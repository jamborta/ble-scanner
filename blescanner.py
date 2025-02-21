from bluepy.btle import Scanner, DefaultDelegate, ScanEntry, Peripheral, ADDR_TYPE_RANDOM
import struct
import math
import paho.mqtt.publish as publish
from mqtt_miflora import MiFlora
import time

def parse_data_type1(data_type1, base_topic):
	data = []
	co2 = struct.unpack(">H", data_type1[20:22])[0]
	data.append({"topic": base_topic + "co2", "payload": co2})
	pm25 = struct.unpack(">H", data_type1[22:24])[0]
	data.append({"topic": base_topic + "pm25", "payload": pm25})
	pm10 = struct.unpack(">H", data_type1[24:26])[0]
	data.append({"topic": base_topic + "pm10", "payload": pm10})
	return data

def parse_data_type2(data_type2, base_topic):
	data = []
	tvoc = struct.unpack(">H", data_type2[20:22])[0]
	data.append({"topic": base_topic + "tvoc", "payload": tvoc})

	rel_temp = (struct.unpack(">H", data_type2[22:24])[0] - 4000) * 0.01
	delta_temp = (struct.unpack("B", bytes([data_type2[24]]))[0]) * 0.1
	temp = rel_temp - delta_temp
	data.append({"topic": base_topic + "temperature", "payload": temp})

	c1 = 17.62
	c2 = 243.12
	fact1 = math.exp((rel_temp * c1) / (rel_temp + c2))
	fact2 = math.exp((temp * c1) / (temp + c2))
	humidity = struct.unpack("B", bytes([data_type2[25]]))[0]
	rel_humidity = humidity * (fact1 / fact2)
	data.append({"topic": base_topic + "humidity", "payload": rel_humidity})
	return data

def parse_govee_h5074(manufacturer_data, base_topic):
	"""Parse H5074 data."""
	data = []
	print("  Raw manufacturer data: %s" % manufacturer_data.hex())
	
	if len(manufacturer_data) == 7:  # New format
		try:
			# Use struct.unpack with little-endian format for H5074
			# h: signed short (temp), H: unsigned short (humidity), B: unsigned byte (battery)
			temp_raw, humidity_raw, battery = struct.unpack("<hHB", manufacturer_data[1:6])
			
			# Scale values appropriately
			temp = temp_raw / 100
			humidity = humidity_raw / 100
			
			print("  Raw values - temp_raw: {}, humidity_raw: {}, battery: {}".format(
				temp_raw, humidity_raw, battery))
			print("  Converted values - temp: {:.2f}°C, humidity: {:.1f}%, battery: {}%".format(
				temp, humidity, battery))
			
			# Only update if values are within reasonable ranges
			if -50 <= temp <= 50:
				data.append({"topic": base_topic + "temperature", "payload": round(temp, 2)})
			if 0 <= humidity <= 100:
				data.append({"topic": base_topic + "humidity", "payload": round(humidity, 1)})
			if 0 <= battery <= 100:
				data.append({"topic": base_topic + "battery", "payload": battery})
				
		except Exception as e:
			print("  Error parsing data: %s" % str(e))
	
	elif len(manufacturer_data) >= 15:  # Old format
		try:
			# Temperature is in bytes 8-10 (little-endian)
			temp_raw = int.from_bytes(manufacturer_data[8:10], byteorder='little', signed=True)
			temp = temp_raw / 100
			
			# Humidity is in byte 12
			humidity = manufacturer_data[12]
			
			# Battery is in byte 15
			battery = manufacturer_data[15] if len(manufacturer_data) > 15 else 0
			
			print("  Raw values (old format) - temp_raw: {} (0x{:04x}), humidity_raw: {} (0x{:02x})".format(
				temp_raw, temp_raw, humidity, humidity))
			print("  Converted values (old format) - temp: {:.2f}°C, humidity: {}%, battery: {}%".format(
				temp, humidity, battery))
			
			if -50 <= temp <= 50:
				data.append({"topic": base_topic + "temperature", "payload": round(temp, 2)})
			if 0 <= humidity <= 100:
				data.append({"topic": base_topic + "humidity", "payload": humidity})
			if 0 <= battery <= 100:
				data.append({"topic": base_topic + "battery", "payload": battery})
		except Exception as e:
			print("  Error parsing data: %s" % str(e))
	
	return data

class ScanDelegate(DefaultDelegate):
	def __init__(self):
		DefaultDelegate.__init__(self)

	def handleDiscovery(self, dev, isNewDev, isNewData):
		if isNewDev:
			print("Discovered device", dev.addr)
		elif isNewData:
			print("Received new data from", dev.addr)

if __name__ == '__main__':	
	scanner = Scanner().withDelegate(ScanDelegate())
	miflora_scanner = MiFlora()
	aranet_mac = "ec:f0:0e:49:34:d8"

	while(True):
		try:
			devices = scanner.scan(10.0)
			print("Found %d devices" % len(devices))
		except Exception as e:
			print(e)
			time.sleep(600)
			continue

		# Process all discovered devices
		for dev in devices:
			# Check if it's the Aranet device
			if dev.addr == aranet_mac:
				if len(dev.rawData) >= 22:
					raw_data = dev.rawData[3:]
					data_type = "%02x" % struct.unpack("<B", bytes([raw_data[18]]))[0]
					if data_type[1] == '1':
						data = parse_data_type1(raw_data, "openhab/am/")
					elif data_type[1] == '2':
						data = parse_data_type2(raw_data, "openhab/am/")
					else:
						data = []
					print("Aranet data:", data)
					publish.multiple(data, hostname="localhost", port=1883, keepalive=60, will=None, auth=None, tls=None)
			
			# Check for Govee devices
			scan_data = dev.getScanData()
			is_govee = False
			
			# First check for Govee service UUID or device name
			for (adtype, desc, value) in scan_data:
				if adtype == 2 or adtype == 3:  # Complete or Incomplete List of 16-bit Service UUIDs
					if "ec88" in value.lower():
						is_govee = True
						break
				elif adtype == 9:  # Complete Local Name
					if "Govee_H5074" in value:
						print("Found Govee device by name: %s" % value)
						is_govee = True
						break
			
			if is_govee:
				# Look for the manufacturer data
				for (adtype, desc, value) in scan_data:
					if adtype == 255:  # Manufacturer Specific Data
						try:
							manufacturer_data = bytes.fromhex(value)
							data = parse_govee_h5074(manufacturer_data, "openhab/govee/%s/" % dev.addr.replace(':', ''))
							if data:
								print("Govee data:", data)
								publish.multiple(data, hostname="localhost", port=1883, keepalive=60, will=None, auth=None, tls=None)
						except Exception as e:
							print("Error processing device %s: %s" % (dev.addr, str(e)))
							continue

		sleep_s = 300
		print("\nSleeping for %s seconds" % sleep_s)
		time.sleep(sleep_s)




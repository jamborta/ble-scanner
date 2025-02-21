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
	
	if len(manufacturer_data) >= 15:  # Adjust length check for the new format
		try:
			# Print raw bytes for debugging
			raw_temp = manufacturer_data[12:14].hex()  # Changed position
			raw_humidity = manufacturer_data[14:15].hex()  # Changed position
			battery = manufacturer_data[15] if len(manufacturer_data) > 15 else 0  # Battery might be here
			print("  Raw values - temp: {}, humidity: {}, battery: {}".format(raw_temp, raw_humidity, battery))
			
			# Temperature: decode as signed 16-bit integer
			temp_raw = int.from_bytes(manufacturer_data[12:14], byteorder='little', signed=True)
			temp = temp_raw / 1000  # Changed scale factor from 100 to 1000
			
			# Humidity: single byte percentage
			humidity = manufacturer_data[14]  # Direct percentage
			
			print("  Converted values - temp: {}°C, humidity: {}%, battery: {}%".format(temp, humidity, battery))
			
			# Only append valid readings (filter out obviously wrong values)
			if -50 <= temp <= 50:  # reasonable temperature range
				data.append({"topic": base_topic + "temperature", "payload": round(temp, 2)})
			if 0 <= humidity <= 100:  # valid humidity range
				data.append({"topic": base_topic + "humidity", "payload": round(humidity, 2)})
			if 0 <= battery <= 100:  # valid battery percentage range
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
							print("  Raw manufacturer data: %s" % manufacturer_data.hex())
							data = parse_govee_h5074(manufacturer_data, "openhab/govee/%s/" % dev.addr.replace(':', ''))
							if data:
								print("Govee data:", data)
								publish.multiple(data, hostname="localhost", port=1883, keepalive=60, will=None, auth=None, tls=None)
						except Exception as e:
							print("Error processing device %s: %s" % (dev.addr, str(e)))
							continue

		sleep_s = 600
		print("\nSleeping for %s seconds" % sleep_s)
		time.sleep(sleep_s)




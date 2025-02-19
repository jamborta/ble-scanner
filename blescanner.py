from bluepy.btle import Scanner, DefaultDelegate, ScanEntry
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
	if len(manufacturer_data) == 8:
		temp = int.from_bytes(manufacturer_data[3:5], byteorder='little') / 100
		humidity = int.from_bytes(manufacturer_data[5:7], byteorder='little') / 100
		battery = manufacturer_data[7]
		
		data.append({"topic": base_topic + "temperature", "payload": temp})
		data.append({"topic": base_topic + "humidity", "payload": humidity})
		data.append({"topic": base_topic + "battery", "payload": battery})
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
			print("\nChecking device: %s" % dev.addr)
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
			for (adtype, desc, value) in scan_data:
				print("  Adtype: %d, Desc: %s" % (adtype, desc))
				if adtype == 255:  # Manufacturer Specific Data
					print("  Found manufacturer data: %s" % value)
					try:
						manufacturer_data = bytes.fromhex(value)
						print("  Manufacturer prefix: %s" % manufacturer_data[0:2].hex())
						if len(manufacturer_data) > 0 and manufacturer_data[0:2] == b'\x88\xec':  # Govee prefix
							print("Found Govee device: %s" % dev.addr)
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




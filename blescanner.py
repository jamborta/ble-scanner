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

def parse_govee_h5074_exact(data_hex, base_topic):
    """Parses Govee H5074 BLE advertisement data with precise humidity correction."""
    data_bytes = bytes.fromhex(data_hex)

    # Ensure the data has the expected minimum length
    if len(data_bytes) < 7:
        raise ValueError("Data is too short to be valid")

    if len(data_bytes) == 7:
		# Extract temperature and humidity from the correct positions
        temp, humi = struct.unpack("<hB", data_bytes[-6:-3])  # Correct byte alignment

		# Convert temperature and humidity to proper values
        temperature = temp / 100.0
        humidity = humi

        data = []
        data.append({"topic": base_topic + "temperature", "payload": temperature})
        data.append({"topic": base_topic + "humidity", "payload": round(humidity, 2)})
        return data

class ScanDelegate(DefaultDelegate):
	def __init__(self):
		DefaultDelegate.__init__(self)

	def handleDiscovery(self, dev, isNewDev, isNewData):
		if isNewDev:
			pass
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
							print("Processing Govee device:", dev.addr, "with data:", value)
							data = parse_govee_h5074_exact(value, "openhab/govee/%s/" % dev.addr.replace(':', ''))
							if data:
								print("Govee data:", data)
								publish.multiple(data, hostname="localhost", port=1883, keepalive=60, will=None, auth=None, tls=None)
						except Exception as e:
							print("Error processing device %s: %s" % (dev.addr, str(e)))
							continue

		sleep_s = 300
		print("\nSleeping for %s seconds" % sleep_s)
		time.sleep(sleep_s)




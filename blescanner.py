from bluepy.btle import Scanner, DefaultDelegate, ScanEntry
import struct
import math
import paho.mqtt.publish as publish
import time

class ScanDelegate(DefaultDelegate):
	def __init__(self, mac):
		self.mac = mac
		DefaultDelegate.__init__(self)

	@staticmethod
	def parse_data_type1(data_type1, base_topic):
		data = []
		co2 = struct.unpack(">H", data_type1[20:22])[0]
		data.append({"topic": base_topic + "co2", "payload": co2})
		pm25 = struct.unpack(">H", data_type1[22:24])[0]
		data.append({"topic": base_topic + "pm25", "payload": pm25})
		pm10 = struct.unpack(">H", data_type1[24:26])[0]
		data.append({"topic": data_type1 + "pm10", "payload": pm10})
		return data

	@staticmethod
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

	def handleDiscovery(self, dev, isNewDev, isNewData):
		if isNewDev:
			print("Discovered device", dev.addr)
		elif isNewData:
			print("Received new data from", dev.addr)
			if dev.addr == self.mac:
				raw_data = dev.rawData[3:]
				data_type = "%02x" % struct.unpack("<B", bytes([raw_data[18]]))[0]
				if data_type[1] == '1':
					data = self.parse_data_type1(raw_data, "openhab/am/")
				elif data_type[1] == '2':
					data = self.parse_data_type2(raw_data, "openhab/am/")
				else:
					data = []
				print(data)
				publish.multiple(data, hostname="localhost", port=1883, keepalive=60, will=None, auth=None, tls=None)


if __name__ == '__main__':
	scanner = Scanner().withDelegate(ScanDelegate(mac="ec:f0:0e:49:34:d8"))

	while(True):
		devices = scanner.scan(10.0)
		sleep_s = 30
		print("Sleeping for %s seconds" % sleep_s)
		time.sleep(sleep_s)




import math
import struct
import bluetooth._bluetooth as bluez
import paho.mqtt.publish as publish
import time

# start bluetooth service: hciconfig hci0 up

class BLE(object):
	LE_META_EVENT = 0x3e
	LE_PUBLIC_ADDRESS = 0x00
	LE_RANDOM_ADDRESS = 0x01
	LE_SET_SCAN_PARAMETERS_CP_SIZE = 7
	OGF_LE_CTL = 0x08
	OCF_LE_SET_SCAN_PARAMETERS = 0x000B
	OCF_LE_SET_SCAN_ENABLE = 0x000C
	OCF_LE_CREATE_CONN = 0x000D

	LE_ROLE_MASTER = 0x00
	LE_ROLE_SLAVE = 0x01

	# these are actually subevents of LE_META_EVENT
	EVT_LE_CONN_COMPLETE = 0x01
	EVT_LE_ADVERTISING_REPORT = 0x02
	EVT_LE_CONN_UPDATE_COMPLETE = 0x03
	EVT_LE_READ_REMOTE_USED_FEATURES_COMPLETE = 0x04

	# Advertisment event types
	ADV_IND = 0x00
	ADV_DIRECT_IND = 0x01
	ADV_SCAN_IND = 0x02
	ADV_NONCONN_IND = 0x03
	ADV_SCAN_RSP = 0x04

	def packed_bdaddr_to_string(self, bdaddr_packed):
		return ':'.join('%02x' % i for i in struct.unpack("<BBBBBB", bdaddr_packed[::-1]))

	def hci_enable_le_scan(self):
		self.hci_toggle_le_scan(0x01)

	def hci_disable_le_scan(self):
		self.hci_toggle_le_scan(0x00)

	def hci_toggle_le_scan(self, enable):
		cmd_pkt = struct.pack("<BB", enable, 0x00)
		bluez.hci_send_cmd(self.sock, self.OGF_LE_CTL, self.OCF_LE_SET_SCAN_ENABLE, cmd_pkt)

	def le_handle_connection_complete(self, pkt):
		pass

	def parse_events(self, mac="ec:f0:0e:49:34:d8"):
		base_topic = "openhab/am/"
		while True:
			sock = bluez.hci_open_dev(0)
			flt = bluez.hci_filter_new()
			bluez.hci_filter_all_events(flt)
			bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
			sock.setsockopt(bluez.SOL_HCI, bluez.HCI_FILTER, flt)
			pkt = sock.recv(255)
			sock.close()
			ptype, event, plen = struct.unpack("BBB", pkt[:3])
			if event == self.LE_META_EVENT:
				subevent, = struct.unpack("B", pkt[3])
				pkt = pkt[4:]
				if subevent == self.EVT_LE_CONN_COMPLETE:
					self.le_handle_connection_complete(pkt)
				elif subevent == self.EVT_LE_ADVERTISING_REPORT:
					num_reports = struct.unpack("B", pkt[0])[0]
					for i in range(0, num_reports):
						mac_address = self.packed_bdaddr_to_string(pkt[3:9])
						print mac_address
						data = []
						if mac == mac_address and len(pkt) > 14:
							air_mentor_package = pkt[13:]
							# low byte of the variable
							data_type = "%02x" % struct.unpack("<B", air_mentor_package[18])[0]
							if data_type[1] == '1':
								co2 = struct.unpack(">H", air_mentor_package[20:22])[0]
								data.append({"topic": base_topic + "co2", "payload": co2})
								pm25 = struct.unpack(">H", air_mentor_package[22:24])[0]
								data.append({"topic": base_topic + "pm25", "payload": pm25})
								pm10 = struct.unpack(">H", air_mentor_package[24:26])[0]
								data.append({"topic": base_topic + "pm10", "payload": pm10})
							elif data_type[1] == '2':
								tvoc = struct.unpack(">H", air_mentor_package[20:22])[0]
								data.append({"topic": base_topic + "tvoc", "payload": tvoc})

								rel_temp = (struct.unpack(">H", air_mentor_package[22:24])[0] - 4000) * 0.01
								delta_temp = (struct.unpack("B", air_mentor_package[24])[0]) * 0.1
								temp = rel_temp - delta_temp
								data.append({"topic": base_topic + "temperature", "payload": temp})

								c1 = 17.62
								c2 = 243.12
								fact1 = math.exp((rel_temp * c1) / (rel_temp + c2))
								fact2 = math.exp((temp * c1) / (temp + c2))
								humidity = struct.unpack("B", air_mentor_package[25])[0]
								rel_humidity = humidity * (fact1 / fact2)
								data.append({"topic": base_topic + "humidity", "payload": rel_humidity})

							print data
							publish.multiple(data, hostname="localhost", port=1883, keepalive=60, will=None, auth=None, tls=None)
							time.sleep(60)

if __name__ == '__main__':
	b = BLE()
	b.parse_events()

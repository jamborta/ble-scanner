import sys
from struct import unpack
import paho.mqtt.publish as publish
from gattlib import DiscoveryService, GATTRequester, GATTResponse

verbose = True

# service = DiscoveryService("hci0")
# if asking for root, try restarting service (hciconfig hci0 down, hciconfig hci0 up)
# to make this work downgrade the firmware (rpi2) sudo rpi-update 33a6707cf1c96b8a2b5dac2ac9dead590db9fcaa
# devices = service.discover(15)

a = ["C4:7C:8D:61:99:B3", "C4:7C:8D:61:92:49", "C4:7C:8D:61:95:E9"]

baseTopic = "openhab/miflower/"
msgs = []

for address in a:
	try:
		topic = baseTopic + address.replace(':', '') + '/'
		requester = GATTRequester(address, True)
		# Read battery and firmware version attribute
		data = requester.read_by_handle(0x0038)[0]
		battery, firmware = unpack('<B6s', data)
		msgs.append({'topic': topic + 'battery', 'payload': battery})
		msgs.append({'topic': topic + 'firmware', 'payload': firmware})
		# Enable real-time data reading
		requester.write_by_handle(0x0033, str(bytearray([0xa0, 0x1f])))
		# Read plant data
		data = requester.read_by_handle(0x0035)[0]
		temperature, sunlight, moisture, fertility = unpack('<hxIBHxxxxxx', data)
		msgs.append({'topic': topic + 'temperature', 'payload': temperature / 10.})
		msgs.append({'topic': topic + 'sunlight', 'payload': sunlight})
		msgs.append({'topic': topic + 'moisture', 'payload': moisture})
		msgs.append({'topic': topic + 'fertility', 'payload': fertility})
		requester.disconnect()
		if (verbose):
			print("name: {}, address: {}".format("Flower care", address))
			print "Battery level:", battery, "%"
			print "Firmware version:", firmware
			print "Light intensity:", sunlight, "lux"
			print "Temperature:", temperature / 10., " C"
			print "Soil moisture:", moisture, "%"
			print "Soil fertility:", fertility, "uS/cm"
	except:
		print "Error during reading:", sys.exc_info()[0]

if (len(msgs) > 0):
	publish.multiple(msgs, hostname="localhost", port=1883, keepalive=60, will=None, auth=None,
					 tls=None)

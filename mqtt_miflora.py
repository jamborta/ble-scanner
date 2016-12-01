import sys
from struct import unpack
import paho.mqtt.publish as publish
from gattlib import DiscoveryService, GATTRequester, GATTResponse

verbose = True


# install milora from git clone https://github.com/open-homeautomation/miflora
# install python 3.5 from source (http://stackoverflow.com/questions/37079195/how-do-you-update-to-the-latest-python-3-5-1-version-on-a-raspberry-pi)
# sudo python3.5 setup.py install


from miflora.miflora_poller import MiFloraPoller, MI_CONDUCTIVITY, MI_MOISTURE, MI_LIGHT, MI_TEMPERATURE, MI_BATTERY

plant1 = MiFloraPoller("C4:7C:8D:61:95:E9")
plant2 = MiFloraPoller("C4:7C:8D:61:92:49")
plant3 = MiFloraPoller("C4:7C:8D:61:95:E9")

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

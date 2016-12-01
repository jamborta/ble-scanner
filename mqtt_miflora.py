import sys
import paho.mqtt.publish as publish
from miflora.miflora_poller import MiFloraPoller, MI_CONDUCTIVITY, MI_MOISTURE, MI_LIGHT, MI_TEMPERATURE, MI_BATTERY
import time

# install milora from git clone https://github.com/open-homeautomation/miflora
# install python 3.5 from source (http://stackoverflow.com/questions/37079195/how-do-you-update-to-the-latest-python-3-5-1-version-on-a-raspberry-pi)
# sudo python3.5 setup.py install

plant1 = MiFloraPoller("C4:7C:8D:61:95:E9")
plant2 = MiFloraPoller("C4:7C:8D:61:92:49")
plant3 = MiFloraPoller("C4:7C:8D:61:95:E9")

plants = [plant1, plant2, plant3]


baseTopic = "openhab/miflower/"
msgs = []

for plant in plants:

	try:
		print("Getting data from Mi Flora")
		print("FW: {}".format(plant.firmware_version()))
		print("Name: {}".format(plant.name()))
		print("Temperature: {}".format(plant.parameter_value(MI_TEMPERATURE)))
		print("Moisture: {}".format(plant.parameter_value(MI_MOISTURE)))
		print("Light: {}".format(plant.parameter_value(MI_LIGHT)))
		print("Conductivity: {}".format(plant.parameter_value(MI_CONDUCTIVITY)))
		print("Battery: {}".format(plant.parameter_value(MI_BATTERY)))

		topic = baseTopic + plant.firmware_version() + '/'
		# Read battery and firmware version attribute
		msgs.append({'topic': topic + 'battery', 'payload': plant.parameter_value(MI_BATTERY)})
		msgs.append({'topic': topic + 'firmware', 'payload': plant.firmware_version()})
		msgs.append({'topic': topic + 'temperature', 'payload': plant.parameter_value(MI_TEMPERATURE)})
		msgs.append({'topic': topic + 'light', 'payload': plant.parameter_value(MI_LIGHT)})
		msgs.append({'topic': topic + 'moisture', 'payload': plant.parameter_value(MI_MOISTURE)})
		msgs.append({'topic': topic + 'fertility', 'payload': plant.parameter_value(MI_CONDUCTIVITY)})
	except:
		print("Error during reading:", sys.exc_info()[0])

	if len(msgs) > 0:
		publish.multiple(msgs, hostname="localhost", port=1883, keepalive=60, will=None, auth=None, tls=None)

	time.sleep(60)
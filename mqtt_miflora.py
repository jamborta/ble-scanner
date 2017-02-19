import sys
import paho.mqtt.publish as publish
from miflora.miflora_poller import MiFloraPoller, MI_CONDUCTIVITY, MI_MOISTURE, MI_LIGHT, MI_TEMPERATURE, MI_BATTERY
import time

# install milora from git clone https://github.com/open-homeautomation/miflora
# install python 3.5 from source (http://stackoverflow.com/questions/37079195/how-do-you-update-to-the-latest-python-3-5-1-version-on-a-raspberry-pi)
# sudo python3.5 setup.py install

plant1 = MiFloraPoller("C4:7C:8D:61:95:E9", cache_timeout=900)
plant2 = MiFloraPoller("C4:7C:8D:61:92:49", cache_timeout=900)
plant3 = MiFloraPoller("C4:7C:8D:61:99:B3", cache_timeout=900)
plant4 = MiFloraPoller("C4:7C:8D:62:A3:55", cache_timeout=900)
plant5 = MiFloraPoller("C4:7C:8D:62:A2:D0", cache_timeout=900)
plant6 = MiFloraPoller("C4:7C:8D:62:99:7E", cache_timeout=900)
plant7 = MiFloraPoller("C4:7C:8D:62:A0:C5", cache_timeout=900)
plant8 = MiFloraPoller("C4:7C:8D:62:9A:B4", cache_timeout=900)

plants = [plant1, plant2, plant3, plant4, plant5, plant6, plant7, plant8]


baseTopic = "openhab/miflower/"
msgs = []

while True:

	for plant in plants:

		try:
			print("Getting data from Mi Flora")
			print("MAC address: {}".format(plant._mac))
			print("FW: {}".format(plant.firmware_version()))
			print("Name: {}".format(plant.name()))
			print("Temperature: {} C".format(plant.parameter_value(MI_TEMPERATURE)))
			print("Moisture: {}".format(plant.parameter_value(MI_MOISTURE)))
			print("Light: {} lux".format(plant.parameter_value(MI_LIGHT)))
			print("Conductivity: {} uS/cm".format(plant.parameter_value(MI_CONDUCTIVITY)))
			print("Battery: {} %".format(plant.parameter_value(MI_BATTERY)))
			if plant.parameter_value(MI_MOISTURE) <= 100:
				topic = baseTopic + plant._mac.replace(":", "") + '/'
				# Read battery and firmware version attribute
				msgs.append({'topic': topic + 'battery', 'payload': plant.parameter_value(MI_BATTERY)})
				msgs.append({'topic': topic + 'firmware', 'payload': plant.firmware_version()})
				msgs.append({'topic': topic + 'temperature', 'payload': plant.parameter_value(MI_TEMPERATURE)})
				msgs.append({'topic': topic + 'light', 'payload': plant.parameter_value(MI_LIGHT)})
				msgs.append({'topic': topic + 'moisture', 'payload': plant.parameter_value(MI_MOISTURE)})
				msgs.append({'topic': topic + 'fertility', 'payload': plant.parameter_value(MI_CONDUCTIVITY)})
		except:
			print("Error during reading:", sys.exc_info()[0])

		print(msgs)
		if len(msgs) > 0:
			publish.multiple(msgs, hostname="localhost", port=1883, keepalive=60, will=None, auth=None, tls=None)

	time.sleep(900)

#!/usr/bin/env python3

import paho.mqtt.client as mqtt
import ssl
import time

MQTT_PORT = 8883
MQTT_KEEPALIVE_INTERVAL = 45
MQTT_TOPIC = 'gps-data'
MQTT_MAG = 'This is the message'

MQTT_HOST = 'data.iot.us-east-1.amazonaws.com'

SECRET_DIR = 'secure'
EDGE_FILE_PREFIX = '{}/eedaa33860'.format(SECRET_DIR)

CA_CERT   = '{}/AmazonRootCA1.pem'.format(SECRET_DIR)

EDGE_CERT = '{}-certificate.pem.crt'.format(EDGE_FILE_PREFIX)
EDGE_PRIV = '{}-private.pem.key'.format(EDGE_FILE_PREFIX)

def on_publish(client, userdata, mid):
	pass

# Create client
mqttc = mqtt.Client()

# Retister publish cb
mqttc.on_publish = on_publish

# Configure TLS info
mqttc.tls_set(
	CA_CERT,
	certfile=EDGE_CERT,
	keyfile=EDGE_PRIV,
	cert_reqs=ssl.CERT_REQUIRED,
	tls_version=ssl.PROTOCOL_TLSv1_2,
	ciphers=None
)

# Connect to MQTT Broker
mqttc.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE_INTERVAL)
mqttc.loop_start()

counter = 0
while True:
	mqttc.publish(MQTT_TOPIC, MQTT_MSG + str(counter), qos=1)
	counter += 1
	time.sleep(1)

mqttc.disconnect()

if __name == '__main__':
	pass

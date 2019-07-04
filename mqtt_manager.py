#!/usr/bin/env python3

import dateutil.parser
import json
import paho.mqtt.client as mqtt
import platform
import redis
import ssl
import time

MQTT_PORT = 8883
MQTT_KEEPALIVE_INTERVAL = 45

# Found using `aws iot describe-endpoint --endpoint-type iot:Data-ATS`
MQTT_HOST = 'a3k87eovjwrlv1-ats.iot.us-east-1.amazonaws.com'

SECRET_DIR = 'secure'
EDGE_FILE_PREFIX = '{}/eedaa33860'.format(SECRET_DIR)

CA_CERT   = '{}/AmazonRootCA1.pem'.format(SECRET_DIR)

EDGE_CERT = '{}-certificate.pem.crt'.format(EDGE_FILE_PREFIX)
EDGE_PRIV = '{}-private.pem.key'.format(EDGE_FILE_PREFIX)

r = redis.Redis()

def on_publish(client, userdata, mid):
	print('Published data')
	pass

if __name__ == '__main__':
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

	try:
		while True:
			while r.llen('gpsentries') > 0:
				keyid = r.lindex('gpsentries', 0).decode()

				entryid = 'gpsdata:{}'.format(keyid)
				data = {k.decode(): v.decode() for (k, v) in r.hgetall(entryid).items()}

				data.update({'datetime': dateutil.parser.parse(keyid).timestamp()})
				msg = json.dumps(data)

				mqttc.publish('gps-data/{}'.format(platform.node()), msg, qos=1)
				print('Published [{}]: {}'.format(platform.node(), msg))

				# After everything else, so that if we have an error, the data can be
				# retransmitted later
				r.delete(entryid)
				r.lpop('gpsentries')

			# Sleep so we don't overwelm the broker
			time.sleep(1)

	except KeyboardInterrupt:
		pass

	mqttc.disconnect()

	pass

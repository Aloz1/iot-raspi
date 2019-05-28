#!/usr/bin/env python3

import argparse
import gatt
import pynmea2
import logging
import redis

logger = logging.getLogger(__name__)

r = redis.Redis()

class GenericDevice(gatt.Device):
	def connect_succeeded(self):
		super().connect_succeeded()
		logger.info("Connected to [{}]".format(self.mac_address))
	
	def connect_failed(self, error):
		super().connect_failed(error)
		logger.info("Connection failed [{}]: {}".format(self.mac_address, error))
	
	def disconnect_succeeded(self):
		super().disconnect_succeeded()
		logger.info("Disconnected [{}]".format(self.mac_address))
	
	def services_resolved(self):
		super().services_resolved()

		logger.info("Resolved services [{}]".format(self.mac_address))
		for service in self.services:
			logger.info("\t[{}] Service [{}]".format(self.mac_address, service.uuid))
			for characteristic in service.characteristics:
				logger.info("\t\tCharacteristic [{}]".format(characteristic.uuid))

	def characteristic_enable_notifications_succeeded(self, characteristic):
		logger.debug('Successfully enabled notifications for chrstc [{}]'.format(characteristic.uuid))

	def characteristic_enable_notifications_failed(self, characteristic, error):
		logger.debug('Failed to enabled notifications for chrstc [{}]: {}'.format(characteristic.uuid, error))
	

	def find_service(self, uuid):
		for service in self.services:
			if service.uuid == uuid:
				return service

		return None

	def find_characteristic(self, service, uuid):
		for chrstc in service.characteristics:
			if chrstc.uuid == uuid:
				return chrstc

		return None

class GPSDevice(GenericDevice):
	SERVICE_UUID_UART      = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
	CHARACTERISTIC_UUID_TX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
	CHARACTERISTIC_UUID_RX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

	class NextPackage:
		def __init__(self):
			self.datestamp = None
			self.timestamp = None
			self.lat = None
			self.lng = None
			self.alt = None
			self.gps_qual = 0
			self.num_sats = 0
			self.h_dil = None
			self.speed = None
			self.dir   = None

		def __repr__(self):
			msg =  '{}(datestamp={},timestamp={},lat={},lng={},alt={},gps_qual={},num_sats={},speed={},dir={})'
			return msg.format(
					type(self).__name__,
					repr(self.datestamp),
					repr(self.timestamp),
					repr(self.lat),
					repr(self.lng),
					repr(self.alt),
					repr(self.gps_qual),
					repr(self.num_sats),
					repr(self.speed),
					repr(self.dir))

		def is_valid(self):
			return (self.datestamp is not None and
					self.timestamp is not None and
					self.lat is not None and
					self.lng is not None and
					self.alt is not None and
					self.speed is not None and
					self.dir is not None)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.buffer = ''
		self.next_package = self.NextPackage()

	def services_resolved(self):
		super().services_resolved()

		service = self.find_service(self.SERVICE_UUID_UART)
		chrstc = self.find_characteristic(service, self.CHARACTERISTIC_UUID_RX)
		chrstc.enable_notifications()
	
	def characteristic_value_updated(self, characteristic, value):
		self.buffer += value.decode()
		split = self.buffer.splitlines()

		# Fix buffer and split so that we don't have half lines
		if len(split) >= 0:
			if len(split[-1]) >= 3 and split[-1][-3] == '*':
				self.buffer = ''
			else:
				self.buffer = split[-1]
				split = split[0:-1]

		for line in split:
			try:
				msg = pynmea2.parse(line)

				logger.debug(line)

				# Parse input
				if isinstance(msg, pynmea2.GGA):
					self.next_package.timestamp = msg.timestamp
					self.next_package.lat = msg.lat + msg.lat_dir
					self.next_package.lng = msg.lon + msg.lon_dir
					self.next_package.alt = '{:3f}{}'.format(msg.altitude, msg.altitude_units)
					self.next_package.gps_qual = msg.gps_qual
					self.next_package.num_sats = msg.num_sats
				elif isinstance(msg, pynmea2.RMC):
					self.next_package.datestamp = msg.datestamp
					self.next_package.speed = msg.spd_over_grnd * 1.852 # Convert to KM/H
					self.next_package.dir = msg.true_course

					if (self.next_package.is_valid() and msg.status == 'A'
							and self.next_package.gps_qual < 5):
						logger.debug(str(self.next_package))
						# Do redis stuff here
						pass

					self.next_package = self.NextPackage()

			except pynmea2.ChecksumError as e:
				((msg, line),) = e.args

				logger.info('NMEA: {}: Skipping sentence'.format(msg))
				logger.debug('\t{}'.format(line))

			except pynmea2.ParseError as e:
				((msg, line),) = e.args

				logger.warn('NMEA: {}: Skipping sentence'.format(msg))
				logger.debug('\t{}'.format(line))

		

class IMUDevice(GenericDevice):
	SERVICE_UUID_UART        = "0000ffe0-0000-1000-8000-00805f9b34fb"
	CHARACTERISTIC_UUID_UART = "0000ffe1-0000-1000-8000-00805f9b34fb"

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.buffer = ''

	def services_resolved(self):
		super().services_resolved()

		service = self.find_service(self.SERVICE_UUID_UART)
		chrstc = self.find_characteristic(service, self.CHARACTERISTIC_UUID_UART)
		chrstc.enable_notifications()
	
	def characteristic_value_updated(self, characteristic, value):
		self.buffer += value.decode()
		split = self.buffer.splitlines()
		self.buffer = split[-1]

		for i in split[0:-1]:
			# Need to parse input and push accel x y z, gyro x y z, mag x y z and temp
			pass
		
class AnyDeviceManager(gatt.DeviceManager):

	# For now, device mac addresses are hard coded into the program. An enhancement for the
	# future is a registration system, whereby nodes could be registered with this edge device
	# to add their mac addresses to a database.
	registered_device_macs = {
			"3c:71:bf:84:b3:86" : GPSDevice
	}

	def device_discovered(self, device):
		#logging.debug('Found device [{}] type "{}"'.format(device.mac_address, type(device)))
		if type(device) is not gatt.Device and not device.is_connected():
			logging.debug('Attempting connection with [{}]'.format(device.mac_address))
			device.connect()
	
	def make_device(self, mac_address):
		if mac_address not in self.registered_device_macs:
			return gatt.Device(manager=self, mac_address=mac_address)

		return self.registered_device_macs[mac_address](manager=self, mac_address=mac_address)


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-v', '--verbose', action='count', default=0)
	args = parser.parse_args()

	levels = [logging.WARNING, logging.INFO, logging.DEBUG]
	logging.basicConfig(level=levels[min(len(levels) - 1, args.verbose)])

	logger.warning('Level WARNING')
	logger.info('Level INFO')
	logger.debug('Level DEBUG')

	manager = AnyDeviceManager('hci0')
	manager.start_discovery()

	try:
		manager.run()
	except KeyboardInterrupt:
		manager.remove_all_devices()
		manager.stop()

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
		pass

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
		logger.debug('Got characteristic value [{}]: {}'.format(str(characteristic.uuid), value.decode()))

		self.buffer += value.decode()
		split = self.buffer.splitlines()
		self.buffer = split[-1]

		for line in split[0:-1]:
			logger.debug(line)
			msg = pynmea2.parse(line)
			# Should probably parse input and only push lat-long and other data
			if isinstance(msg, pynmea2.GGA):
				# timestamp
				# lat
				# lat_dir - N/S
				# lon
				# lon_dir - E/W
				# gps_qual - FIX AVAIL (0 - no, 1 - yes, 2 - differential)
				# num_sats
				# horizontal_dil - Horizontal Dilution of precision
				# altitude_units - Altitude above sea level
				# geo_sep - Ignore
				# geo_sep_units - Ignore
				# age_gps_data - Differential GPS age
				pass
			elif isinstance(msg, pynmea2.RMC):
				# timestamp
				# status - 'A' = Data valid, 'V' = Data not valid
				# lat
				# lat_dir - N/S
				# lon
				# lon_dir - E/W
				# spd_over_grnd - Knots
				# true_course - Degrees from north
				# datestamp
				# mag_variation - Not used
				# mag_var - 'A' = Autonomous, 'D' = Differential, 'E' = Estimated
				pass
			elif isinstance(msg, pynmea2.VTG):
				# true_track - True bearing
				# true_track_sym - True bearing reference (always 'T' for true)
				# mag_track - Magnetic bearing
				# mag_track_sym - Magnetic bearing reference (always 'M' for magnetic)
				# spd_over_grnd_kts - Horizontal ground speed in knots
				# spd_over_grnd_knts_sym - N for knots
				# spd_over_grnd_kmph - Horizontal ground speed in km/h
				# spd_over_grnd_kmph_sym - K for kilometers
				# faa_mode - 'A' = autonomous, 'D' = Differential, 'E' = Estimated
				pass

			logger.debug(str(line))
		

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
		logging.debug('Found device [{}] type "{}"'.format(device.mac_address, type(device)))
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
		for device in manager.devices():
			if device.is_connected():
				device.disconnect()

		manager.stop()

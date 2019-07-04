# IoT vehicle tracking - edge application
A simple project demonstrating an IoT approach to vehicle tracking. The project has 3 software
components: node devices, the edge device, and the web client. Node devices notify the edge device
of new data via BLE GATT, which is then fetched by the edge device and cached locally in a redis
database. Data is then pushed to the cloud (AWS) via MQTT. When AWS receives data via MQTT, it is
stored in a dynamodb for later retreival. Finally, this data is pulled by the web client and presented
as both a table of values and a path on google maps (for GPS data).

This repository is specifically for the edge device application. For other software components,
please see their corresponding repositories (in the [Other repositories](#other-repositories)
section below).

# Edge application
The edge application is divided into 2 main services which may be run independent of each other.
These services are the GATT manager and the MQTT manager. The GATT manager is responsible for
communications between nodes and the edge device, whilst the MQTT manager facilitates communications
with the cloud. By dividing the application into 2 separate services, we're able to perform both
operations concurrently, without having to worry about one blocking the other. Additionally,
communications between both services is bridged using the redis database, which gives us local
caching for free.

## GATT manager
The GATT manager listens for, and connects to nearby registered GATT devices, and receives any data
from GATT notifications. As this project is a proof of concept, there is currently no registration
system, instead BLE MAC addresses are hard coded into the GATT manager. A future addition would be
a simple registration system, however that was beond the scope of the proof of concept. Once a
connection to a BLE device has been established, GATT manager will listen for events on the relevant
GATT services and characteristics. When a notification is received, the incoming block of data is
pushed to a local buffer. Once a newline, carriage return, or EOF is received, the buffer (up until
the special character) is interpreted and constructed into a JSON string, which is pushed to the
redis database for later retrieval by the MQTT manager.

## MQTT manager
The MQTT manager poles the redis database for more data, and pushes the data up to the cloud via
MQTT. Theoretically, `mqtt_manager.py` could connect to any MQTT broker, but for the purpose of this
project, I've chosen Amazon AWS for it's simplicity to setup. There isn't really much to say about
the manager, as it is a fairly simple piece of software.

# Setup and usage
First setup a virtual environment and install all requirements:
```
> python3 -m virtualenv venv
> source venv/bin/activate
> pip install -r requirements.txt
```

Download the relevant certificates and keys, and place them in the `secure` directory. The directory
should contain an Amazon root certificate (named `AmazonRootCA1.pem`), an IoT device private key and
corresponding certificate. These should be created/acquired as per Amazon's documentation. The names
of the Iot private key and certificate may differ from what is written in the `mqtt_manager.py`
file, hence the names of the files, or the contents of `mqtt_manager.py` should be changed
accordingly.

Finally, ensure redis is installed and running on the same machine.

If all goes well, you can start `gatt_manager.py` and `mqtt_manager.py`.

# Other repositories
- [Node firmware](https://github.com/Aloz1/iot-nodes)
- [Web client](https://github.com/Aloz1/iot-website)

# The report
For more details, take a look at the [corresponding report](https://github.com/Aloz1/iot-report)

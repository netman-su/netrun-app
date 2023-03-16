
![Logo](https://netmanshop.com/static/logoWide.png)


# Netrun

Netrun is a community-driven Python application that assists with network device discovery and inventory management. Netrun uses SSH connections to retrieve device information and parses the output to build a detailed inventory of your network infrastructure.



## How it Works

Netrun is a powerful tool for managing your network inventory and ensuring that your network devices are running the latest operating system (OS) versions. When Netrun connects to a device, it retrieves the model and OS version for that device, making it easy to keep track of all the devices in your network.

In addition to its inventory management capabilities, Netrun can also compare the OS version of a device against the public Netrun RESTful API. This API provides a comprehensive database of the latest OS versions for a wide range of network hardware, making it easy to identify when a device's OS is out of date.

To query the latest OS version for a device, Netrun requires valid Netrun and/or Cisco ASD credentials, which are stored in the configurations.json file. The Cisco ASD credentials are used to access the Cisco ASD API, which provides additional information on the latest OS versions for Cisco hardware that is not available through Netrun alone.

When Netrun identifies that a device's OS version is greater than what the Netrun API returns, it reports the OS version for that hardware back to the Netrun database. This drives the community aspect of the application, allowing others to programmatically and easily check their devices against a free and public database of devices. This feature also ensures that the database remains up-to-date with the latest OS versions for all supported hardware.
## Installation

Clone the repository:

```bash
  git clone https://github.com/netman-su/netrun-app.git
```

Install the dependencies:
```bash
  pip install -r requirements.txt
```

(Optional) Create and copy the following to netrun\config\configurations.json and fill in the necessary credentials.
```json
{
    "netrun_update": true,
    "netrun_username": "SSH username",
    "netrun_password": "SSH password",
    "netrun_token": "token or null",
    "ciscoClientId": "token or null",
    "ciscoClientSecret": "token or null"
}
```
    
## Usage/Examples

Netrun can be used to discover network devices and add them to an inventory database. The scan() method accepts the IP address of a device and, optionally, its device ID and name. If no IP address is provided, Netrun will attempt to scan all devices in the inventory.

```python
from netrun import netrun

n = netrun()

# Scan a single device
n.scan(device_ip="192.168.1.1", device_id="cisco_ios")

# Scan all devices in inventory
n.scan()
```

Netrun can also import devices from a CSV file using the scan_file() method. The CSV file should have three columns: IP address, device ID, and track status.

```python
n.scan_file("devices.csv")
```

Additionally, you can just run both of these from the command line. You can provide arguments to scan specific devices or import devices from a CSV file. For example:

```bash
python netrun -scan 192.168.1.1 cisco_ios true
python netrun -file \Path\To\Devices\File.csv
```

## FAQ

#### How do I get API access to Netrun?

For now, we will be handling requests manually. Feel free to contact us at info@netmanshop.com and we'll get you your API token as soon as possible. (For the record, we're not storing your information for anything other than API auditing. That would be lame.)

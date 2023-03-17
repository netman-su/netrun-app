import re
import csv
import runner
import hashlib
import ipaddress
import api.cisco_api as cisco_api
import api.netrun_api as netrun_api
import config.operations as operations


class netrun:

    def __init__(self) -> None:
        self.credentials, self.netrun_track, self.devices, self.nodes = operations.initialize()

    def validate_device_ip(self, device_ip):
        try:
            ipaddress.ip_address(device_ip)
        except ValueError:
            raise Exception(f"[{device_ip}] is not a valid IP address")

    def scan(self, device_ip=None, device_id=None, device_name=None):
        data = self.nodes
        device_dict = self.devices
        credentials = self.credentials
        track = self.netrun_track

        # If nothing is supplied, check every node
        if device_ip is None:
            for node in data.values():
                self.scan(device_ip=node['ip'], device_id=node['type'],
                          credentials=credentials, device_name=node['name'], track=node['track'])

        else:
            # Validate IP
            self.validate_device_ip(device_ip)

            # Check if IP exists in loaded database
            node_id_found = False
            for d in data.values():
                if device_ip in d.values():
                    new_id = [i for i in data if data[i]["ip"] == device_ip][0]
                    device_id = data[str(new_id)]['type']
                    node_id_found = True
                    break

            # Hashing generates "unique" node IDs
            if not node_id_found:
                new_id = self.hash_string(device_ip, 'md5')

                # Using Netmiko's SSHDetect module if device_id isn't supplied
                if device_id == None:
                    print(
                        'Device ID not provided, attempting to auto-detect device type')
                    device_id = runner.guesser(device_ip, credentials)

            # Check if supplied device_id and options are supported
            device = device_dict.get(device_id)
            if not device:
                raise Exception(
                    f"Device type [{device_id}] not found in dictionary, refer to documentation")

            # Send runner to verify connectivity
            try:
                print("Attempting to connect to", device_ip)
                results, hostname = runner.runner(device_ip, device_id, credentials, [
                                                  device["show_version"], device["show_model"]], device_name)
                print("Successfully connected to", device_ip)
            except Exception as e:
                data[str(new_id)] = {}
                raise e

            # Parse first two items in results (version, model)
            parse_dict = self.parse(device_id, results)

            # Add node data to nodes.json dictionary object
            node = {
                "name": device_name if device_name else hostname,
                "ip": device_ip,
                "type": device_id,
                "version": parse_dict["version"],
                "latest": self.get_latest_version(list(parse_dict["inventory"])[0], parse_dict["version"], device["software_track"]) if track else None,
                "track": track,
                "inventory": parse_dict["inventory"]
            }
            data[str(new_id)] = node

            self.update_netrun_db(list(node["inventory"])[0], node["version"], node["latest"], self.netrun_track)
    
            # Update nodes.json
            operations.update_nodes(data)

            return node

    # Mass import with a .csv, expected order is IP, device type, track status
    # The track field looks for anything to return True, doesn't matter what you add
    def scan_file(self, file):
        with open(file, newline='') as csvfile:
            file_reader = csv.reader(csvfile)
            for row in file_reader:
                try:
                    if len(row) >= 2:
                        device_ip, device_id = row[0], row[1]
                        self.scan(device_ip, device_id)
                    else:
                        device_ip = row[0]
                        self.scan(device_ip)
                except Exception as e:
                    print(e)

    # Parsing logic for the device dictionary. This loads position logic for parsing SSH output.
    def parse_device_dict(self, device_id):
        device_dict = self.devices
        parse_logic = device_dict[device_id]["parse_logic"]

        return {
            "model_position": parse_logic["model_position"],
            "version_position": parse_logic["version_position"],
            "serial_position": parse_logic["serial_position"],
        }

    # Parsing logic for Cisco devices
    def parse_inventory(self, input_list, positions):
        parse_dict = {"inventory": {}}

        pid_pattern = re.compile(rf'{positions["model_position"]}')
        sn_pattern = re.compile(rf'{positions["serial_position"]}')

        current_pid = None
        current_sn = None

        for line in input_list:
            pid = re.search(pid_pattern, line)
            sn = re.search(sn_pattern, line)

            if pid:
                current_pid = pid.group(1)
            if sn:
                current_sn = sn.group(1)

            if current_pid and current_sn:
                if current_pid in parse_dict["inventory"]:
                    if current_sn not in parse_dict["inventory"][current_pid]:
                        parse_dict["inventory"][current_pid].append(current_sn)
                else:
                    parse_dict["inventory"][current_pid] = [current_sn]
                current_pid = None
                current_sn = None

        return parse_dict

    # Parsing logic for software versioning. Works with just one for now, other vendors may make this require more functions.
    def parse_version(self, version_list, positions):
        version_pattern = re.compile(rf'{positions["version_position"]}')

        for line in version_list:

            if "," in line:
                line = line.replace(',', '')

            version = re.search(version_pattern, line)

            if version:
                version = version.string
                if bool(re.search('\.0[1-9A-Za-z]', version)) == True:
                    version = version.replace('0', '')

                return {"version": version}

    # Uses other parse functions to return a dictionary that netrun.scan() can work with
    def parse(self, device_id, results):
        positions = self.parse_device_dict(device_id)

        model_list = results[1].splitlines()
        version_list = results[0].split()

        parse_dict = self.parse_inventory(model_list, positions)
        parse_dict.update(self.parse_version(version_list, positions))

        return parse_dict
    
    def get_latest_version(self, model, version, trackable=bool):
        if trackable:
            latest = cisco_api.call(model, version)
            if latest is None:
                latest = netrun_api.get(model, version)
        if not trackable:
            latest = netrun_api.get(model, version)
        
        return latest
    
    def update_netrun_db(self, model, version, latest, netrun_track = bool):
            if netrun_track == True:
                if latest:
                    netrun_api.add(model, latest)
                else:
                    netrun_api.add(model, version)

    def hash_string(self, string, algorithm):
        algorithms = {
            "md5": hashlib.md5(),
            "sha256": hashlib.sha256()
        }

        hash = algorithms[algorithm]
        hash.update(string.encode())
        return hash.hexdigest()

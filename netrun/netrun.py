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
        self.config, self.devices = operations.initialize()

    def validate_device_ip(self, device_ip):
        try:
            ipaddress.ip_address(device_ip)
        except ValueError:
            raise Exception(f"[{device_ip}] is not a valid IP address")

    def scan(self, device_ip=None, device_id=None, device_name=None):
        device_dict = self.devices
        credentials = [self.config['netrun_username'], self.config['netrun_password']]
        track = self.config['netrun_track']

        # If no device_ip is provided, scan all nodes.
        if device_ip is None:
            print("Scanning all nodes")
            data = operations.get_all_from_table('nodes')
            for node in data:
                self.scan(device_ip=node['ip'], device_id=node['type'], device_name=node['name'])
            return

        print(f"Scanning {device_ip}")
        # Validate IP address.
        self.validate_device_ip(device_ip)

        # Find the node ID in the loaded database.
        node_id_found = False
        if operations.get_from_nodes('ip', device_ip):
            temp_var = operations.get_from_nodes('ip', device_ip)
            new_id = temp_var[0]['node_id']
            device_id = temp_var[0]['type']
            node_id_found = True

        # Generate a unique node ID using hashing if not found.
        if not node_id_found:
            new_id = self.hash_string(device_ip, 'md5')

            # Attempt to auto-detect the device type if device_id is not provided.
            if device_id is None:
                print('Device ID not provided, attempting to auto-detect device type')
                device_id = runner.guesser(device_ip, credentials)

        # Check if the supplied device_id is supported.
        device = device_dict.get(device_id)
        if not device:
            raise Exception(f"Device type [{device_id}] not found in dictionary, refer to documentation")

        # Establish and verify connectivity with the device.
        try:
            print(f"Attempting to connect to {device_ip}")
            results, hostname = runner.runner(device_ip, device_id, credentials, [
                device["show_version"], device["show_model"], device["show_run"]], device_name)
            
            print(f"Successfully connected to {device_ip}")
        except Exception as e:
            data[str(new_id)] = {}
            raise e

        # Parse version and model information from results.
        parsed_data = self.parse(device_id, results)

        # Construct node data object.
        node = {
            "name": device_name if device_name else hostname,
            "ip": device_ip,
            "type": device_id,
            "version": parsed_data["version"],
            "latest": self.get_latest_version(list(parsed_data["inventory"])[0], 
                        parsed_data["version"], device["software_track"]) if track else None,
            "track": track,
            "inventory": parsed_data["inventory"],
            "configuration": parsed_data["configuration"]
        }

        self.update_netrun_db(list(node["inventory"])[0], node["version"], node["latest"], track)
        
        # Update nodes.json file.
        operations.insert_into_nodes(new_id, node)

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
                    print(f"Error scanning {row}: {e}")

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

        running_config = results[2]
        model_list = results[1].splitlines()
        version_list = results[0].split()
        
        parse_dict = self.parse_inventory(model_list, positions)
        parse_dict.update(self.parse_version(version_list, positions))
        parse_dict.update({"configuration": operations.compress_config(running_config)})

        return parse_dict
    
    def get_latest_version(self, model, version, trackable=bool):
        if trackable:
            print("  Calling Cisco")
            latest = cisco_api.call(self.config['ciscoClientId'], self.config['ciscoClientSecret'], model, version)
            if latest is None:
                print("  Cisco call failed, calling netrun db")
                latest = netrun_api.get(self.config['netrun_token'], model)
        if not trackable:
            print("  Calling netrun db")
            latest = netrun_api.get(self.config['netrun_token'], model)
        
        return latest
    
    def update_netrun_db(self, model, version, latest, netrun_track = bool):
            if netrun_track == True:
                print("  Updating netrun db")
                if latest:
                    netrun_api.add(self.config['netrun_token'], model, latest)
                else:
                    netrun_api.add(self.config['netrun_token'], model, version)

    def hash_string(self, string, algorithm):
        algorithms = {
            "md5": hashlib.md5(),
            "sha256": hashlib.sha256()
        }

        hash = algorithms[algorithm]
        hash.update(string.encode())
        return hash.hexdigest()

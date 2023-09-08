import os
import re
import csv
import runner
import hashlib
import logging
import ipaddress
import utils.api.cisco_api as cisco_api
import utils.api.netrun_api as netrun_api
import utils.database.operations as operations


class netrun:

    def __init__(self, log_to_file=False) -> None:
            self.config, self.devices = operations.initialize()

            # Define logger for this class
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.DEBUG)

            # Default console handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter('%(levelname)s-%(name)s: %(message)s')
            console_handler.setFormatter(console_formatter)
            
            if log_to_file:
                # File handler
                self.logfile = os.path.join(os.getcwd(), "netrun_log.txt")  # define your log file path here
                file_handler = logging.FileHandler(self.logfile)
                file_formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
                file_handler.setFormatter(file_formatter)
                self.logger.addHandler(file_handler)
            else:
                self.logger.addHandler(console_handler)

    def validate_device_ip(self, device_ip):
        try:
            ipaddress.ip_address(device_ip)
        except ValueError:
            raise Exception(f" [{device_ip}] is not a valid IP address")

    def scan(self, device_ip=None, device_id=None, device_name=None):
        """
        Scan a single device or all nodes. If no IP is provided, all nodes are scanned.
        """

        # Handle case where no IP is provided, delegate to scan_all method
        if device_ip is None:
            self.scan_all()
            return

        self.logger.info(f"Scanning [{device_ip}]")
        self.validate_device_ip(device_ip)  # Ensure the IP address is valid

        # Query for existing node information in the loaded database
        node_entry = operations.select_from_table_search('nodes', 'ip', device_ip)

        if node_entry:  # If node details are found in the database
            new_id, device_id = node_entry[0]['node_id'], node_entry[0]['type']
        else:  # Generate new ID via hashing
            new_id, device_id = self.hash_string(device_ip, 'md5'), None

        # Auto-detection of device type if ID is not provided
        if device_id is None:
            self.logger.info('Auto-detecting device type...')
            device_id = runner.guesser(device_ip, [self.config['netrun_username'], self.config['netrun_password']])

        # Verify that the provided device_id exists in the devices dictionary
        device = self.devices.get(device_id)
        if device is None:
            raise Exception(f"Device type [{device_id}] not found in dictionary, refer to documentation")
        
        # Establish and verify connectivity with the device,
        # then gather necessary data
        try:
            self.logger.info(f"Connecting to [{device_ip}]...")
            commands = [device[key] for key in ["show_version", "show_model", "show_run"]]
            results, hostname = runner.runner(device_ip, device_id, [self.config['netrun_username'], self.config['netrun_password']], commands)
        except Exception as e:
            self.logger.exception(e)
            raise
 
        parsed_results = self.parse(device_id, results)  # Parse version and model information from results

        # Construct the node data object
        node = {
            "node_id": new_id,
            "name": device_name or hostname,
            "ip": device_ip,
            "type": device_id,
            "version": parsed_results["version"],
            "latest": self.get_latest_version(list(parsed_results["inventory"])[0], parsed_results["version"],
                                              device["software_track"]) if self.config['netrun_track'] else None,
            "track": self.config['netrun_track'],
            "inventory": parsed_results["inventory"],
            "configuration": parsed_results["configuration"]
        }

        # Update local and database
        self.update_netrun_db(list(node["inventory"])[0], node["version"], node["latest"], self.config['netrun_track'])
        operations.insert_or_update('nodes', node)

        self.logger.info(f"Scan complete.")
        return node
    
    def scan_all(self):
        self.logger.info("Scanning all nodes")
        data = operations.select_all_from_table('nodes')
        for node in data:
            try:
                self.scan(device_ip=node['ip'], device_id=node['type'], device_name=node['name'])
            except Exception as e:
                self.logger.error(f"Error scanning {node['ip']}: {e}")
        return

    def scan_file(self, file):
        """
        Mass scan against csv, only required field is device_ip
        """
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
                    self.logger.error(f"Error scanning {row}: {e}")

    def prepare_positions(self, device_id):
        """
        Prepare parsing logic for the device dictionary.
        This loads position logic for parsing SSH output.
        """
        parse_logic = self.devices[device_id]["parse_logic"]
        
        return {
            "model_position": parse_logic["model_position"],
            "version_position": parse_logic["version_position"],
            "serial_position": parse_logic["serial_position"],
        }
        
    def parse_inventory(self, inventory_lines, positions):
        """
        Parses inventory lines into a structured dictionary.
        Follows the pattern specified in `positions`.
        """
        inventory = {}
        current_pid, current_sn = None, None

        pid_pattern = re.compile(positions["model_position"])
        sn_pattern = re.compile(positions["serial_position"])

        for line in inventory_lines:
            pid_match = pid_pattern.search(line)
            sn_match = sn_pattern.search(line)

            current_pid = pid_match.group(1) if pid_match else current_pid
            current_sn = sn_match.group(1) if sn_match else current_sn

            if current_pid and current_sn:
                # check if the current_pid is already in inventory
                if current_pid not in inventory:
                    inventory[current_pid] = [current_sn]
                else:
                    # check if the current_sn is already in the list for current_pid
                    if current_sn not in inventory[current_pid]:
                        inventory[current_pid].append(current_sn)

                current_pid, current_sn = None, None

        return {"inventory": inventory}
        
    def extract_version(self, version_list, positions):
        """
        Extracts software version from the given list.
        Uses regex pattern in `positions` for extraction.
        """
        version_pattern = re.compile(positions["version_position"])

        for line in (line.replace(",", "") for line in version_list):
            match = version_pattern.search(line)
            
            if match:
                version = match.string
                return {"version": version.replace('0', '') if bool(re.search('\.0[1-9A-Za-z]', version)) else version}
        
    def parse(self, device_id, results):
        """
        Uses the helper functions to parse the results into a structured dictionary.
        """
        positions = self.prepare_positions(device_id)

        running_config = results[2]
        model_list = results[1].splitlines()
        version_list = results[0].split()
        
        parsed_results = self.parse_inventory(model_list, positions)
        parsed_results.update(self.extract_version(version_list, positions))
        parsed_results["configuration"] = operations.compress_config(running_config)

        return parsed_results
    
    def get_latest_version(self, model, version, trackable=bool):
        """Fetches the latest version either from Cisco or NetMan API.
        Uses Cisco API if trackable, otherwise hits the NetMan API"""
        
        if trackable and self.config.get('ciscoClientId') and self.config.get('ciscoClientSecret'):
            self.logger.info(f"Fetching latest [{model}] version from Cisco...")
            latest = cisco_api.call(self.config['ciscoClientId'], self.config['ciscoClientSecret'], model)
            if latest is None:
                self.logger.info("Cisco fetch failed, fetching NetMan...")
                latest = netrun_api.get(self.config['netrun_token'], model)
        else:
            self.logger.info(f"Fetching latest [{model}] version from NetMan...")
            latest = netrun_api.get(self.config['netrun_token'], model)
        
        return latest
        
    def update_netrun_db(self, model, version, latest, netrun_track=bool):
        """Updates model version in NetMan db.
        If netrun tracking is enabled, updates either with the latest version or the provided version"""

        if netrun_track and self.config.get('netrun_token'):
            version_to_add = latest or version
            self.logger.info(f"Comparing [{model} | {version_to_add}] against NetMan...")
            netrun_api.add(self.config['netrun_token'], model, version_to_add)

    def hash_string(self, string, algorithm):
        algorithms = {
            "md5": hashlib.md5(),
            "sha256": hashlib.sha256()
        }

        hash = algorithms[algorithm]
        hash.update(string.encode())
        return hash.hexdigest()

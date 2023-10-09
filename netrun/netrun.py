import os
import re
import csv
import runner
import hashlib
import logging
import ipaddress
import utils.api.netrun_api as netrun_api
import utils.database.operations as operations
import utils.strategies.strategies as strageties


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

            self.strategies = {
                'NetMan': strageties.NetManStrategy,
                'cisco': strageties.CiscoStrategy,
                'palo': strageties.PaloAltoStrategy,
                # Add new vendors here...
            }

    def validate_device_ip(self, device_ip):
        try:
            ipaddress.ip_address(device_ip)
        except ValueError:
            raise Exception(f" [{device_ip}] is not a valid IP address")
        
    def scan_all_if_no_IP(self, device_ip):
        if device_ip is None:
            self.scan_all()
            return True
        return False

    def validate_scanned_device(self, device_ip):
        self.validate_device_ip(device_ip)
        node_entry = operations.select_from_table_search('nodes', 'ip', device_ip)
        return node_entry

    def handle_device_not_in_db(self, device_ip, node_entry):
        if node_entry:
            new_id, device_id = node_entry[0]['node_id'], node_entry[0]['type']
        else:
            new_id, device_id = self.hash_string(device_ip, 'md5'), None
        return new_id, device_id

    def infer_device_type(self, device_id, device_ip):
        if device_id is None:
            self.logger.info('Auto-detecting device type...')
            device_id = runner.guesser(device_ip, [self.config['netrun_username'], self.config['netrun_password']])
        return device_id

    def perform_device_scan(self, device, device_ip, device_id):
        try:
            self.logger.info(f"Connecting to [{device_ip}]...")
            commands = [device[key] for key in ["show_version", "show_model", "show_run"]]
            results, hostname = runner.runner(device_ip, device_id, [self.config['netrun_username'], self.config['netrun_password']], commands)
        except Exception as e:
            self.logger.exception(e)
            raise 
        return results, hostname

    def construct_node(self, device_id, results, new_id, device_name, device_ip):
        parsed_results = self.parse(device_id, results)
        self.node = {
            "node_id": new_id,
            "name": device_name,
            "ip": device_ip,
            "type": device_id,
            "version": parsed_results["version"],
            "latest": None,
            "track": self.config['netrun_track'],
            "inventory": parsed_results["inventory"],
            "configuration": parsed_results["configuration"]
        }

        if self.node['track']:
            self.node['latest'] = self.get_latest_version(self.node, self.devices[device_id]['manufacturer'], self.devices[device_id]['software_track'])

        return self.node

    def scan(self, device_ip=None, device_id=None, device_name=None):
        if self.scan_all_if_no_IP(device_ip):
            return

        self.logger.info(f"Scanning [{device_ip}]")
        node_entry = self.validate_scanned_device(device_ip)
        new_id, device_id = self.handle_device_not_in_db(device_ip, node_entry)
        device_id = self.infer_device_type(device_id, device_ip)

        device = self.devices.get(device_id)
        if device is None:
            raise Exception(f"Device type [{device_id}] not found in dictionary, refer to documentation")
        
        results, hostname = self.perform_device_scan(device, device_ip, device_id)
        node = self.construct_node(device_id, results, new_id, device_name if device_name else hostname, device_ip)

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
    
    def get_latest_version(self, node, company, trackable=bool):
        """ Fetches the latest version either from Cisco or NetMan API
        Uses Cisco API if trackable, otherwise hits the NetMan API"""

        strategy = self.strategies['NetMan']  # Default strategy

        if trackable:
            strategy = self.strategies[company]

        strategy_instance = strategy(node, self.config, self.logger)
        version = strategy_instance.get_version()

        if not version:
            strategy = self.strategies['NetMan']
            strategy_instance = strategy(node, self.config, self.logger)
            version = strategy_instance.get_version()
            if not version:
                return None
        
        return version
        
    def update_netrun_db(self, model, version, latest, netrun_track=bool):
        """Updates model version in NetMan db.
        If netrun tracking is enabled, updates either with the latest version or the provided version"""

        if netrun_track and self.config.get('netrun_token'):
            version_to_add = latest or version
            self.logger.info(f"Comparing [{model} | {version_to_add}] against NetMan...")
            netrun_api.add(self.config['netrun_token'], model, version_to_add, self.logger)

    def hash_string(self, string, algorithm):
        algorithms = {
            "md5": hashlib.md5(),
            "sha256": hashlib.sha256()
        }

        hash = algorithms[algorithm]
        hash.update(string.encode())
        return hash.hexdigest()

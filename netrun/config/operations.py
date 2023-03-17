import os
import json

def initialize():
    # File path operations
    script_dir = os.path.dirname(os.path.realpath(__file__))
    node_path = os.path.join(script_dir, 'nodes.json')
    dictionary_path = os.path.join(script_dir, 'device_dictionary.json')
    config_path = os.path.join(script_dir, 'configurations.json')

    # Load configurations
    while True:
        try:
            with open(config_path, "r") as config_json:
                config_json = json.load(config_json)
                credentials = [config_json["netrun_username"], config_json["netrun_password"]]
                netrun_track = config_json["netrun_track"]
            break
        except FileNotFoundError:
            print("Config file not found, creating")
            config = {
                "netrun_track": True,
                "netrun_username": input("Username for netrun SSH operations: "),
                "netrun_password": input("Password for netrun SSH operations: "),
                "netrun_token": input("Token for netrun API: "),
                "ciscoClientId": None,
                "ciscoClientSecret": None
            }
            with open(config_path, "w") as config_json:
                json.dump(config, config_json, indent=4)

    # Load node data
    while True:
        try:
            with open(node_path, "r") as node_list:
                nodes = json.load(node_list)
                break
        except FileNotFoundError:
            print("Node file not found, creating")
            nodes = {}
            with open(node_path, "w") as node_list:
                json.dump(nodes, node_list, indent=4)

    # Load device dictionary
    while True:
        try:
            with open(dictionary_path, "r") as device_json:
                devices = json.load(device_json)
                break
        except FileNotFoundError:
            raise "Device dictionary not found"
    
    return credentials, netrun_track, devices, nodes

def get_config_value(key):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(script_dir, 'configurations.json')
    with open(config_path, "r") as f:
        data = json.load(f)
    return data.get(key)

def update_nodes(data):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    node_path = os.path.join(script_dir, 'nodes.json')
    with open(node_path, "w") as json_update:
        json.dump(data, json_update, indent=2)
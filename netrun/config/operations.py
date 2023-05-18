import os
import json
import zlib
import base64

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

def find_item_recursively(search_item, data, return_parent=False, search_keys=True, search_values=True):
    for key, value in data.items():
        if (search_keys and key == search_item) or (search_values and value == search_item):
            return value if not return_parent else data
        if isinstance(value, dict):
            nested_item = find_item_recursively(search_item, value, return_parent, search_keys, search_values)
            if nested_item is not None:
                return nested_item
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    nested_item = find_item_recursively(search_item, item, return_parent, search_keys, search_values)
                    if nested_item is not None:
                        return nested_item
    return None

def get_config_value(search_value, search_file, return_parent=False, search_keys=True, search_values=True):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(script_dir, search_file)
    
    with open(config_path, "r") as f:
        data = json.load(f)

    return find_item_recursively(search_value, data, return_parent, search_keys, search_values)

def update_nodes(data):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    node_path = os.path.join(script_dir, 'nodes.json')
    with open(node_path, "w") as json_update:
        json.dump(data, json_update, indent=2)

def compress_config(config_text):
    compressed_data = zlib.compress(config_text.encode('utf-8'))
    encoded_data = base64.b64encode(compressed_data)
    return encoded_data.decode('utf-8')

def decompress_config(encoded_data):
    decoded_data = base64.b64decode(encoded_data.encode('utf-8'))
    decompressed_data = zlib.decompress(decoded_data)
    return decompressed_data.decode('utf-8')

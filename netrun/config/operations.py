import os
import json
import zlib
import base64
import sqlite3

# Connect to SQLite database, if it doesn't exist it will be created
conn = sqlite3.connect('database.db')
c = conn.cursor()

def create_tables():
    # Create table for configs
    c.execute('''CREATE TABLE IF NOT EXISTS config
                (netrun_track TEXT, netrun_username TEXT, netrun_password TEXT, netrun_token TEXT,
                ciscoClientId TEXT, ciscoClientSecret TEXT)''')
    # Create table for nodes
    c.execute('''CREATE TABLE IF NOT EXISTS nodes
                (node_id TEXT UNIQUE, name TEXT, ip TEXT, type TEXT, version TEXT, latest TEXT, track TEXT, configuration TEXT, inventory BLOB)''')
    conn.commit()

def insert_into_config(config_data):
    c.execute('''INSERT INTO config VALUES (?, ?, ?, ?, ?, ?)''', 
                 (config_data['netrun_track'], config_data['netrun_username'], config_data['netrun_password'], config_data['netrun_token'], 
                  config_data['ciscoClientId'], config_data['ciscoClientSecret']))
    conn.commit()

def insert_into_nodes(node_id, node_data):
    # Convert the inventory to json and remove it from node_data
    inventory_json = json.dumps(node_data.pop('inventory'))

    # Create a tuple with all values in the correct order
    values = (node_id, *node_data.values(), inventory_json)

    # Insert these values into the nodes table
    # UPSERT operation (since SQLite 3.24.0)
    c.execute('''
        INSERT INTO nodes(node_id, name, ip, type, version, latest, track, configuration, inventory)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(node_id) DO UPDATE 
        SET name = excluded.name, ip = excluded.ip, type = excluded.type, version = excluded.version,
            latest = excluded.latest, track = excluded.track, configuration = excluded.configuration,
            inventory = excluded.inventory
    ''', values)
    
    conn.commit()

def get_all_from_table(table_name):
    c.execute(f'''SELECT * FROM {table_name}''')
    # Fetch all results from the SELECT statement
    rows = c.fetchall()
    
    # Get the column names from cursor description
    columns = [column[0] for column in c.description]
    
    # Convert each row to a dictionary using column names
    nodes = [dict(zip(columns, row)) for row in rows]
    
    return nodes

def get_from_config():
    c.execute('''SELECT * FROM config''')
    config = c.fetchone()
    return config

def get_from_nodes(search_type, value):
    c.execute(f'''SELECT * FROM nodes WHERE {search_type} = ?''', (value,))
    # Fetch all results from the SELECT statement
    rows = c.fetchall()
    
    # Get the column names from cursor description
    columns = [column[0] for column in c.description]
    
    # Convert each row to a dictionary using column names
    nodes = [dict(zip(columns, row)) for row in rows]
    
    return nodes

def initialize():
    create_tables()
    script_dir = os.path.dirname(os.path.realpath(__file__))
    dictionary_path = os.path.join(script_dir, 'device_dictionary.json')

    try:
        # Check if config data exists
        config = get_from_config()
        if config is None:
            raise sqlite3.OperationalError
        else:
            config_data = {
                'netrun_track': config[0],
                'netrun_username': config[1],
                'netrun_password': config[2],
                'netrun_token': config[3],
                'ciscoClientId': config[4],
                'ciscoClientSecret': config[5]
            }
    except sqlite3.OperationalError:
        print("Config data not found, creating")
        config_data = {
            "netrun_track": input("Enter a value for netrun_track: "),
            "netrun_username": input("Username for netrun SSH operations: "),
            "netrun_password": input("Password for netrun SSH operations: "),
            "netrun_token": input("Token for netrun API: "),
            "ciscoClientId": input("Enter Cisco Client ID for SSH operations: "),
            "ciscoClientSecret": input("Enter Cisco Client Secret for SSH operations: ")
        }
        insert_into_config(config_data)

    # Load device dictionary
    while True:
        try:
            with open(dictionary_path, "r") as device_json:
                devices_data = json.load(device_json)
                break
        except FileNotFoundError:
            raise "Device dictionary not found"

    return config_data, devices_data

def compress_config(config_text):
    compressed_data = zlib.compress(config_text.encode('utf-8'))
    encoded_data = base64.b64encode(compressed_data)
    return encoded_data.decode('utf-8')

def decompress_config(encoded_data):
    decoded_data = base64.b64decode(encoded_data.encode('utf-8'))
    decompressed_data = zlib.decompress(decoded_data)
    return decompressed_data.decode('utf-8')

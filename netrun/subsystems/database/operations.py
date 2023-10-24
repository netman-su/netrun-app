import os
import json
import zlib
import base64
import sqlite3

class DBHandler:
    
    TABLES = {
        "config": [
            "netrun_track TEXT", 
            "netrun_username TEXT", 
            "netrun_password TEXT", 
            "netrun_token TEXT", 
            "ciscoClientId TEXT", 
            "ciscoClientSecret TEXT"
        ],
        "nodes": [
            "node_id TEXT UNIQUE", 
            "name TEXT", 
            "ip TEXT", 
            "type TEXT", 
            "version TEXT", 
            "latest TEXT", 
            "track TEXT", 
            "configuration TEXT", 
            "inventory BLOB"
        ],
    }
    
    def __init__(self):
        self.DB_FILE = self.get_db_path("database.db")
        self.conn = sqlite3.connect(self.DB_FILE)
        self.c = self.conn.cursor()
    
    def get_db_path(self, db_name):
        base_dir = os.getenv('APPDATA') if os.name == 'nt' else os.path.expanduser("~")
        app_dir = os.path.join(base_dir, '.netrun')
        if not os.path.exists(app_dir):
            os.makedirs(app_dir)
        full_db_path = os.path.join(app_dir, db_name)
        return full_db_path
    
    def create_tables(self):
        for table_name in self.TABLES:
            self.c.execute(f'''
                CREATE TABLE IF NOT EXISTS {table_name}
                ({", ".join(self.TABLES[table_name])})
            ''')
        self.c.connection.commit()

    def insert_or_update(self, table_name, data):
        if table_name == "nodes":
            # convert inventory to json
            data['inventory'] = json.dumps(data['inventory'])

        columns = ', '.join(data.keys())
        placeholders = ', '.join('?' * len(data))
        values = tuple(data.values())

        if table_name == "nodes":
            data_no_id = data.copy()
            del data_no_id['node_id']
            update_cols = ', '.join(f'{k}=excluded.{k}' for k in data_no_id.keys())
            self.c.execute(f'''
                INSERT INTO {table_name} ({columns})
                VALUES ({placeholders})
                ON CONFLICT(node_id) DO UPDATE 
                SET {update_cols}
            ''', values)
        else:
            self.c.execute(f'INSERT INTO {table_name} ({columns}) VALUES ({placeholders})', values)
        
        self.c.connection.commit()

    def select_all_from_table(self, table_name):
        self.c.execute(f'SELECT * FROM {table_name}')
        return self.fetch_query_results()

    def select_from_table_search(self, table_name, search_field, value):
        self.c.execute(f'SELECT * FROM {table_name} WHERE {search_field} = ?', (value,))
        return self.fetch_query_results()

    def fetch_query_results(self):
        rows = self.c.fetchall()
        columns = self.get_columns()
        results = [dict(zip(columns, row)) for row in rows]

        # If 'inventory' exists and is an str, translate it back into a dictionary
        for result in results:
            if 'inventory' in result and isinstance(result['inventory'], str):
                result['inventory'] = json.loads(result['inventory']) 

        return results

    def get_columns(self):
        return [column[0] for column in self.c.description]

    def initialize(self):
        self.create_tables()
        script_dir = os.path.dirname(os.path.realpath(__file__))
        dictionary_path = os.path.join(script_dir, 'device_dictionary.json')

        try:
            config = self.select_all_from_table('config')[0]
        except IndexError:
            print("Config data not found, creating")
            config = {
                "netrun_track": input("Enter a value for netrun_track: "),
                "netrun_username": input("Username for netrun SSH operations: "),
                "netrun_password": input("Password for netrun SSH operations: "),
                "netrun_token": input("Token for netrun API: "),
                "ciscoClientId": input("Enter Cisco Client ID for SSH operations: "),
                "ciscoClientSecret": input("Enter Cisco Client Secret for SSH operations: ")
            }
            self.insert_or_update('config', config)

        while True:
            try:
                with open(dictionary_path, "r") as device_json:
                    devices_data = json.load(device_json)
                    break
            except FileNotFoundError:
                raise "Device dictionary not found"
        
        return config, devices_data

    def compress_config(self, config_text):
        compressed_data = zlib.compress(config_text.encode('utf-8'))
        encoded_data = base64.b64encode(compressed_data)
        return encoded_data.decode('utf-8')

    def decompress_config(self, encoded_data):
        decoded_data = base64.b64decode(encoded_data.encode('utf-8'))
        decompressed_data = zlib.decompress(decoded_data)
        return decompressed_data.decode('utf-8')

    def main_get(self, search_term):
        all_nodes = self.select_all_from_table('nodes')
        results = []

        for node in all_nodes:
            for key, value in node.items():
                if search_term == key or search_term == value:
                    results.append(node)
                elif isinstance(value, dict):
                    for inner_key, inner_value in value.items():
                        if search_term == inner_key or search_term in inner_value:
                            results.append(node)
                        elif isinstance(inner_value, list):
                            if search_term in inner_value:
                                results.append(node)
        
        return results

    def main_report(self):
        node_return = self.select_all_from_table('nodes')

        # create empty dictionaries to store data
        data = {'bad': []}
        for node in node_return:
            current = node['version']
            latest = node['latest']
            hostname = node['name']
            if latest and ((current in latest) or (current == latest)):
                pass
            else:
                # create a dictionary for each iteration and append to list
                data['bad'].append({"hostname": hostname, "current": current, "latest": latest})

        # Convert dictionaries into a JSON object
        json_data = json.dumps(data, indent=2)

        return json_data
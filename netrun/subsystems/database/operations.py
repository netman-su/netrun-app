import os
import json
import zlib
import base64
import getpass
import logging
from sqlalchemy import create_engine, Column, Integer, String, Text, text
from sqlalchemy.orm import sessionmaker, validates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Config(Base):
    __tablename__ = 'config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    netrun_track = Column(Text)
    netrun_username = Column(Text)
    netrun_password = Column(Text)
    netrun_token = Column(Text)
    ciscoClientId = Column(Text)
    ciscoClientSecret = Column(Text)


class Node(Base):
    __tablename__ = 'nodes'

    node_id = Column(Text, primary_key=True)
    name = Column(Text)
    ip = Column(Text)
    type = Column(Text)
    version = Column(Text)
    latest = Column(Text)
    track = Column(Text)
    configuration = Column(Text)
    inventory = Column(Text)

    @validates('inventory')
    def validate_inventory(self, key, value):
        return json.dumps(value)


class DBHandler:
    def __init__(self, logger=None):

        if logger is not None:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.DEBUG)

        base_dir = os.getenv('APPDATA') if os.name == 'nt' else os.path.expanduser("~")
        app_dir = os.path.join(base_dir, '.netrun')
        os.makedirs(app_dir, exist_ok=True)
        db_path = os.path.join(app_dir, "database.db")

        self.engine = create_engine(f'sqlite:///{db_path}')
        session = sessionmaker(bind=self.engine)
        self.session = session()
        Base.metadata.create_all(self.engine)

        script_dir = os.path.dirname(os.path.realpath(__file__))
        dictionary_path = os.path.join(script_dir, 'device_dictionary.json')

        while True:
            try:
                with open(dictionary_path, "r") as device_json:
                    self.devices_data = json.load(device_json)
                    break
            except FileNotFoundError:
                raise "Device dictionary not found"
            
        config_query = self.session.query(Config).first()
            
        if config_query is None:        
            questions = [
                {"SSH Username: ": "netrun_username"},
                {"SSH Password: ": "netrun_password"},
                {"API usage? [True|Null]: ": "netrun_track"},
            ]
        
            add_questions_if_true = [
                {"NetMan API Token [Key|Null]: ": "netrun_token"},
                {"Cisco Client ID [Key|Null]: ": "ciscoClientId"},
                {"Cisco Client Secret [Key|Null]: ": "ciscoClientSecret"},
            ]

            config = {}
            for question in questions:
                for text, key in question.items():
                    if 'Password' in text:
                        config[key] = getpass.getpass(prompt=text) or None
                    else:
                        config[key] = input(text) or None

            if config['netrun_track']:
                for question in add_questions_if_true:
                    for text, key in question.items():
                        config[key] = input(text) or None

            self.insert_or_update_config(config)

    def insert_or_update_config(self, data):
        new_config = Config(**data)
        self.session.merge(new_config)
        self.session.commit()

    def insert_or_update_node(self, data):
        # data['inventory'] = json.dumps(data['inventory'])
        new_node = Node(**data)
        self.session.merge(new_node)
        self.session.commit()

    def get_all(self, table_name):
        return self.session.query(globals()[table_name.capitalize()]).all()

    def get_by_search(self, table_name, search_field, value):
        model = globals()[table_name.capitalize()]
        return self.session.query(model).filter(text(f"{search_field}=:value")).params(value=value).all()

    def main_get(self, search_term):
        all_nodes = self.get_all('node')
        results = []
        for node in all_nodes:
            node.inventory = json.loads(node.inventory)
            for key, value in node.__dict__.items():
                if search_term == key or search_term == str(value):
                    results.append(node)
        
        return results

    def main_report(self):
        node_return = self.get_all('node')

        # create empty dictionaries to store data
        data = {'bad': []}
        for node in node_return:
            current = node.version
            latest = node.latest
            hostname = node.name
            if latest and ((current in latest) or (current == latest)):
                pass
            else:
                # create a dictionary and append to list
                data['bad'].append({"hostname": hostname, "current": current, "latest": latest})

        # Convert dictionaries into a JSON object
        json_data = json.dumps(data, indent=2)

        return json_data

    def compress_config(self, config_text):
        compressed_data = zlib.compress(config_text.encode('utf-8'))
        encoded_data = base64.b64encode(compressed_data)
        return encoded_data.decode('utf-8')

    def decompress_config(self, encoded_data):
        decoded_data = base64.b64decode(encoded_data.encode('utf-8'))
        decompressed_data = zlib.decompress(decoded_data)
        return decompressed_data.decode('utf-8')
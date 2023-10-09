import re
from netrun import runner
from ..api import cisco_api
from ..api import netrun_api

class LatestVersionStrategy:
    def __init__(self, node: dict, credentials: dict, logger):
        self.credentials = credentials
        self.logger = logger
        self.node = node
        self.model = list(self.node['inventory'])[0]

    def get_version(self):
        pass 

class NetManStrategy(LatestVersionStrategy):
    def get_version(self):
        self.logger.info(f"Fetching latest [{self.model}] version from NetMan...")
        return netrun_api.get(self.credentials['netrun_token'], self.model, self.logger)

class CiscoStrategy(LatestVersionStrategy):
    def get_version(self):
        self.logger.info(f"Fetching latest [{self.model}] version from Cisco...")
        return cisco_api.call(self.credentials['ciscoClientId'], self.credentials['ciscoClientSecret'], self.model)

class PaloAltoStrategy(LatestVersionStrategy):
    def get_version(self):
        self.logger.info(f"Fetching latest [{self.model}] version from Palo Alto...")
        output = runner.runner(self.node['ip'], self.node['type'], 
                            [self.credentials['netrun_username'], self.credentials['netrun_password']], 
                            ['request system software info'])[0]
        version = re.search(r'(\d+\.\d+\.\d[\S]*)|(\d+\.\d+\.\d+)', output[0]).group(1)
        if not version:
            return None
        return version
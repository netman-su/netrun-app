import re
from netrun.subsystems.runner import runner
from netrun.subsystems.api import cisco
from netrun.subsystems.api import netman

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
        return netman.get(self.credentials[0].netrun_token, self.model, self.logger)

class CiscoStrategy(LatestVersionStrategy):
    def get_version(self):
        self.logger.info(f"Fetching latest [{self.model}] version from Cisco...")
        return cisco.call(self.credentials[0].ciscoClientId, self.credentials[0].ciscoClientSecret, self.model)

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
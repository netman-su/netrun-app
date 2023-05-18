import requests
import json
import logging
from functools import lru_cache
import config.operations as operations

logging.captureWarnings(True)

##
##    function to obtain a new OAuth 2.0 token from the authentication server
##
@lru_cache(maxsize=1)
def get_new_token():

    url = 'https://cloudsso.cisco.com/as/token.oauth2'
    client_id = operations.get_config_value("ciscoClientId", "configurations.json")
    client_secret = operations.get_config_value('ciscoClientSecret', "configurations.json")

    params = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }

    headers = {
        'Content-Type':'application/x-www-form-urlencoded'
    }

    token_response = requests.post(url=url, params=params, headers=headers)
                
    if token_response.status_code == 200:
        return token_response.json()['access_token']
    
    return None

# Chaching results of the same products so we don't have to slam the Cisco API for larger queries
@lru_cache(maxsize=64)
def call(pid, version):

    ## 
    ## 	obtain a token before calling the API for the first time
    ##
    token = get_new_token()

    url = "https://api.cisco.com/software/v4.0/metadata/pidrelease"

    payload = json.dumps({
    "pid": pid,
    "currentReleaseVersion": version,
    "outputReleaseVersion": "latest",
    "pageIndex": "1",
    "perPage": "25"
    })
    headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code == 200:
        response_dict = response.json()
        softwarelist = response_dict['metadata'][0]['products'][0]['softwareTypes']
 
        for software in softwarelist:
            # Software Type Ids for IOS-XE, NXOS and IOS resepctively
            if software['softwareTypeId'] in ['282046477', '282088129', "280805680"]:
                return software['operatingSystems'][0]['releases'][0]['version']

    else:
        return None

def search_dict(data, key, value):
    if isinstance(data, dict):
        for k, v in data.items():
            if k == key and v == value:
                return True
            elif isinstance(v, (dict, list)):
                found = search_dict(v, key, value)
                if found:
                    return True
    elif isinstance(data, list):
        for item in data:
            found = search_dict(item, key, value)
            if found:
                return True
    return False

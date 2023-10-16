import requests
import json
import logging
from functools import lru_cache
import netrun.subsystems.database.operations as operations

logging.captureWarnings(True)

##
##    function to obtain a new OAuth 2.0 token from the authentication server
##
@lru_cache(maxsize=1)
def get_new_token(client_id, client_secret):
    url = 'https://id.cisco.com/oauth2/default/v1/token'

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
def call(client_id, client_secret, pid):

    ## 
    ## 	obtain a token before calling the API for the first time
    ##
    token = get_new_token(client_id, client_secret)

    url = f"https://apix.cisco.com/software/suggestion/v2/suggestions/releases/productIds/{pid}?pageIndex=1"

    payload = {}
    headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    if response.status_code == 200:
        response_dict = response.json()
        softwarelist = response_dict['productList']
 
        for software in softwarelist:
            # Software Type Ids for IOS-XE, NXOS and IOS resepctively
            if software['product']['softwareType'] in ['IOS Software', 'IOS XE Software', 'NX-OS System Software']:
                return software['suggestions'][0]['relDispName']

    else:
        return None
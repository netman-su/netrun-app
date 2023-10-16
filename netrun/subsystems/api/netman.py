import requests
import json
import logging
from functools import lru_cache
import netrun.subsystems.database.operations as operations

logging.captureWarnings(True)

@lru_cache(maxsize=64)
def add(netrun_token, model, version, logger):
    url = "https://api.netmanshop.com/netrun/add"

    payload = json.dumps({
    "model": f"{model}",
    "version": f"{version}"
    })
    headers = {
    'X-Netrun': 'Now this header? *slaps roof* This baby does nothing.',
    'Authorization': f'Bearer {netrun_token}',
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    if response.status_code == 200:
        logger.info(f'Added [{model} | {version}] to NetMan!')

    else:
        logger.error(f'Add failed for [{model} | {version}]: {json.loads(response.text)["error"]}')
        return None
    
@lru_cache(maxsize=64)
def get(netrun_token, model, logger):
    url = "https://api.netmanshop.com/netrun/get"

    payload = json.dumps({
    "model": f"{model}"
    })
    headers = {
    'X-Netrun': 'Now this header? *slaps roof* This baby does nothing.',
    'Authorization': f'Bearer {netrun_token}',
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    if response.status_code == 200:
        response_json = json.loads(response.text)
        latest = response_json['result']['version']
        return latest

    else:
        logger.error(f'Fetch failed for [{model}]: {json.loads(response.text)["error"]}')
        return None
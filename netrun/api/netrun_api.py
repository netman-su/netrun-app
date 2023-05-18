import requests
import json
import logging
from functools import lru_cache
import config.operations as operations

logging.captureWarnings(True)

@lru_cache(maxsize=64)
def add(model, version):
    netrun_token = operations.get_config_value("netrun_token", "configurations.json")
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
        print(f"Added {model} to netrun db")

    else:
        return None
    
@lru_cache(maxsize=64)
def get(model):
    netrun_token = operations.get_config_value("netrun_token", "configurations.json")
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
        return None
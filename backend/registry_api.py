import requests
from requests.auth import HTTPBasicAuth

REGISTRY_URL = "http://private_registry:5000"

USERNAME = "admin"
PASSWORD = "admin123"

def check_registry_alive():
    url = f"{REGISTRY_URL}/v2/"
    response = requests.get(url, auth=HTTPBasicAuth(USERNAME, PASSWORD))
    return response.status_code, response.text

def get_image_repositories():
    url = f"{REGISTRY_URL}/v2/_catalog"
    response = requests.get(url, auth=HTTPBasicAuth(USERNAME, PASSWORD))
    if response.status_code == 200:
        return response.json().get("repositories", [])
    else:
        return []
    
def get_image_tags(image_name):
    url = f"{REGISTRY_URL}/v2/{image_name}/tags/list"
    response = requests.get(url, auth=HTTPBasicAuth(USERNAME, PASSWORD))
    if response.status_code == 200:
        return response.json().get("tags", [])
    else:
        return []
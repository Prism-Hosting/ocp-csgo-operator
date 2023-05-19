"""
Module to probe TCP ports of CS:GO service objects
"""

from openshift.dynamic import DynamicClient
import kopf
import kopf
import kubernetes
import modules.utils as utils
import socket

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#  ------------------------
#           VARS
#  ------------------------
services_cache = []
# For schema, see cache_service()

#  ------------------------
#         FUNCTIONS
#  ------------------------
def cache_service(obj_uuid):
    """
    Return a cached k8s service object.
    If it does not exist, retrieve and cache it.

    Args:
        uuid (string): UUID of the service to probe
        
    Returns:
        dict: {"name": "example", "port": 27015, "uuid": 'UUID-...' }
    """
    
    try:
        if not utils.is_uuid(obj_uuid):
            raise kopf.PermanentError(f"'{obj_uuid}' is not a valid UUID.")
        
        # Check if service is already cached and return it
        for item in services_cache:
            if 'uuid' in item and item["uuid"] == obj_uuid:
                return item
            
        # Service not yet cached: Append to cache and return cached obj
        client = utils.kube_auth()
        
        api = client.resources.get(api_version="v1", kind="Service")
        service = api.get(namespace="prism-servers", label_selector=f"custObjUuid={obj_uuid}").items
        
        if len(service) <= 0:
            raise ValueError("Found no service for this UUID.")
        elif len(service) > 1:
            raise ValueError(f"Found too many services for this UUID, got: {str(len(service))}.")
        
        service_name = service[0]["metadata"]["name"]
        service_uuid = service[0]["metadata"]["labels"]["custObjUuid"]
        service_port = service[0]["spec"]["ports"][0]["port"]
        service_ip = service[0]["spec"]["clusterIP"]
        
        service_object = {
            "name": service_name,
            "uuid": service_uuid,
            "port": service_port,
            "ip": service_ip
        }
        
        services_cache.append(service_object)
            
        return service_object
        
    except Exception as e:
        raise kopf.PermanentError(f"cache_service(): {str(e)}")

def probe_service(obj_uuid):
    """ Probe a service 

    Args:
        uuid (string): UUID of the service to probe
        
    Returns:
        bool: True if SUCCESS, False if FAIL
    """
    
    try:
        if not utils.is_uuid(obj_uuid):
            raise kopf.PermanentError(f"'{obj_uuid}' is not a valid UUID.")

        # Get service from cache
        service = cache_service(obj_uuid)
        
        target_ip = service["ip"]
        target_port = service["port"]
        
        # Set up connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        
        result = sock.connect_ex((target_ip, target_port))
        if result == 0:
            return True
        else:
            return False
        
    except Exception as e:
        raise kopf.PermanentError(f"probe_service(): {str(e)}")
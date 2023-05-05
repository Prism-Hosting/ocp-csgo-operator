"""
Module to automatically port forward
"""

import kopf
import kubernetes
import logging
import os
import uuid
import kopf
import kubernetes
from openshift.dynamic import DynamicClient

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#  ------------------------
#         FUNCTIONS
#  ------------------------
def kube_auth():
    # Attempt logon
    try:
        kubernetes.config.load_incluster_config()
        k8s_client = kubernetes.client.ApiClient()
        dyn_client = DynamicClient(k8s_client)
        
        return dyn_client

    except Exception as e:
        raise kopf.PermanentError(f"Failed to create dynamic client: {str(e)}")

def do_unifi_request(mode, target_url, json=None, cookies=None, csrf_token=None):
    """ Do a general web request, tailored to the Unifi API

    Args:
        mode (string): Type of request
        target_url (string): Target URL
        json (dict): Body dict
        cookies (dict): Cookie dict
        csrf_token (string): CSRF token

    Returns:
        response: Response object
    """
    
    request_headers = {
        "Accept": "*/*",
        "Content-Type": "application/json"
    }
    
    if csrf_token:
        request_headers["X-CSRF-Token"] = csrf_token
    
    try:
        session = requests.Session()
        
        if mode == "get":            
            response = session.get(target_url, headers=request_headers, json=json, cookies=cookies, verify=False)
            
        elif mode == "post":
            response = session.post(target_url, headers=request_headers, json=json, cookies=cookies, verify=False)
            
        else:
            raise ValueError(f"This request mode ({mode}) is unhandled.")
        
        session.close()
            
    except Exception as e:
            raise ValueError(f"Error during request: {str(e)}")   
        
    return response  

def unifi_api_logon():
    """ Logs onto Unifi API

    Returns:
        dict = [ cookies: dict, csrf: string ]
    """
    target_url = f"https://{os.environ['UNIFI_API_HOST']}/api/auth/login"
    auth_payload = {
        "username": os.environ['UNIFI_API_USER'],
        "password": os.environ['UNIFI_API_PASS']
    }
    
    response = do_unifi_request("post", target_url, auth_payload)
    response.raise_for_status()
    
    returnObj = {
        # {'TOKEN': 'ey123...', ""}
        "cookies": response.cookies,
        "csrf": response.headers["X-CSRF-TOKEN"]
    }
    
    return returnObj
    
def create_port_forward_body(target_ip, target_port):
    """ Create UDM SE/PRO port forwarding request body

    Args:
        target_ip (string): IP of host to forward to
        target_port (string): Port (source and dest) to forward

    Returns:
        dict: Request payload
    """
    
    uuid_part = str(uuid.uuid4())[:8]
    body = {
        "pfwd_interface": "wan",
        "name":      f"csgo-server-{uuid_part}",
        "enabled":   True,
        "src":       "any",
        "dst_port":  target_port,
        "fwd":       target_ip,
        "fwd_port":  target_port,
        "proto":     "tcp_udp",
        "log":       False
    }
    
    return body
    
def create_port_forward(target_ip, target_port):
    """ Create UDM SE/PRO port forwarding rule

    Args:
        target_ip (string): IP of host to forward to
        target_port (string): Port (source and dest) to forward
    """
    
    target_url = f"https://{os.environ['UNIFI_API_HOST']}/proxy/network/api/s/default/rest/portforward"
    
    try:
        body = create_port_forward_body(target_ip, target_port)
        response = do_unifi_request("post", target_url, body)
        
        if not response.status_code == 200:
            raise ValueError(f"Status code is {str(response.status_code)} - {response.text}")
        
    except Exception as e:
        print(f"Failed: {str(e)}")
        
def get_port_forward():
    """ Get UDM SE/PRO port forwarding rules
    
    Returns:
        dict: Port forwarding entries
    """
    
    target_url = f"https://{os.environ['UNIFI_API_HOST']}/proxy/network/api/s/default/rest/portforward"
    
    try:
        auth = unifi_api_logon()
        response = do_unifi_request("get", target_url, cookies=auth["cookies"], csrf_token=auth["csrf"])
        
        if not response.status_code == 200:
            raise ValueError(f"Status code is {str(response.status_code)} - {response.text}")
        
    except Exception as e:
        print(f"get_port_forward() failed: {str(e)}")
        
    return response
    
"""
Sample request:
    POST https://<ip>/proxy/network/api/s/default/rest/portforward
    Auth header: Cookie: TOKEN=...
    {
        "name":  "csgo-server-GUID",
        "enabled":  true,
        "pfwd_interface":  "wan",
        "src":  "any",
        "dst_port":  "1234",
        "fwd":  "<targetIp>",
        "fwd_port":  "1234",
        "proto":  "tcp_udp",
        "log":  false
    }
"""
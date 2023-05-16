"""
Module to automatically forwards ports to CS:GO services on a UDM SE.
"""

from openshift.dynamic import DynamicClient
import kopf
import kubernetes
import os
import uuid
import kopf
import datetime
import kubernetes
import modules.utils as utils

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#  ------------------------
#           VARS
#  ------------------------
unifi_auth_data = {
    "data": None,
    "expiry": None
}

#  ------------------------
#         FUNCTIONS
#  ------------------------
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
        response = getattr(session, mode)(target_url, headers=request_headers, json=json, cookies=cookies, verify=False)
        
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
    
    # Only execute if auth has not yet expired
    if unifi_auth_data["expiry"]:
        now = datetime.datetime.now()
        if now < unifi_auth_data["expiry"]:
            # Not yet expired
            return unifi_auth_data["data"]
    
    response = do_unifi_request("post", target_url, auth_payload)
    response.raise_for_status()
    
    returnObj = {
        # {'TOKEN': 'ey123...', ""}
        "cookies": response.cookies,
        "csrf": response.headers["X-CSRF-TOKEN"]
    }
    
    unifi_auth_data["data"] = returnObj
    unifi_auth_data["expiry"] = datetime.datetime.now() + datetime.timedelta(hours=1)
    
    return unifi_auth_data["data"]
    
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
        target_ip (string): IP of host to forward to.
        target_port (string): Port (source and dest) to forward.
    """
    
    target_url = f"https://{os.environ['UNIFI_API_HOST']}/proxy/network/api/s/default/rest/portforward"
    
    try:
        auth = unifi_api_logon()
        body = create_port_forward_body(target_ip, target_port)
        
        response = do_unifi_request("post", target_url, body, cookies=auth["cookies"], csrf_token=auth["csrf"])
        
        if not response.status_code == 200:
            raise ValueError(f"Status code is {str(response.status_code)} - {response.text}")
        
    except Exception as e:
        raise ValueError(f"create_port_forward() error: {str(e)}")

def delete_port_forward(id):
    """ Delete UDM SE/PRO port forwarding rule

    Args:
        target_ip (string): ID of port forward object
    """
    
    target_url = f"https://{os.environ['UNIFI_API_HOST']}/proxy/network/api/s/default/rest/portforward/{id}"
    
    try:
        auth = unifi_api_logon()
        response = do_unifi_request("delete", target_url, cookies=auth["cookies"], csrf_token=auth["csrf"])
        
        if not response.status_code == 200:
            raise ValueError(f"Status code is {str(response.status_code)} - {response.text}")
        
    except Exception as e:
        print(f"delete_port_forward() Error: {str(e)}")
    
    
    return True
        
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
        
    return response.json()

def delete_port_forward_by_ip(ip):
    """ Deletes a port forwarding of a k8s service that was deleted.

    Args:
        ip (string): IP address the service used to have
    """
    
    try:
        forwards = (get_port_forward())["data"]
        for forward in forwards:
            if forward["fwd"] == ip:
                forward_id = forward["_id"]
                delete_port_forward(forward_id)
        
    except Exception as e:
        raise kopf.TemporaryError(f"delete_port_forward_by_ip() error: {str(e)}")

#  ------------------------
#           LOGIC
#  ------------------------
def supervise_ips():
    """
    Supervises services in prism-servers ns and checks if they have an External-IP asigned.
    If yes, checks if a port forwarding rule exists for them.
    """
    
    try:
        client = utils.kube_auth()
        
        api = client.resources.get(api_version="v1", kind="Service")
        items = api.get(namespace="prism-servers", label_selector="custObjUuid").items
        
        forwards = get_port_forward()["data"]
        
        for item in items:
            do_create = False
            do_delete = False
            
            this_port = item.spec.ports[0].port
            this_prismserver_name = item.metadata.ownerReferences[0].name
            
            #print(" ")
            #print(f"Iterating for: {this_prismserver_name}")
            
            # Generic status object
            status_obj = {
                "status": {
                    "forwarding": {
                        "available": True,
                        "phase": None,
                        "message": None,
                        "port": this_port
                    }
                }
            }
            
            # Only proceed if loadBalancer has assigned an IP
            if item.status.loadBalancer:
                this_ip = item.status.loadBalancer.ingress[0].ip
                #print(f"> Has IP: {this_ip}")
                
                if len(forwards) >= 1:
                    for forward in forwards:
                        forward_id = forward["_id"]
                        
                        if forward["fwd"] == this_ip:
                            if forward["fwd_port"] == this_port:
                                #print("> Forward found and it is correct.")
                                
                                # Do this, as otherwise a forwarding will be scheduled anyway if forwards{} has more than one item
                                do_create = False
                                break
                            
                            else:
                                #print(f"> [i] Correcting forward for {this_ip}...")
                                do_delete = True
                                break
                                
                        else:
                            # Forwarding is missing
                            do_create = True

                else:
                    #print(f"> [i] Forwardings were initially empty, creating...")
                    do_create = True
                    
            else:
                raise ValueError("Service does not yet have an external IP assigned.")
            
            # (Re)create port forward
            try:
                if do_delete or do_create:
                    do_status_update = True
                    #print(f"> Creating forward for: {this_port} -> {this_ip}")
                    
                    if do_delete:
                        delete_port_forward(forward_id)
                        
                    create_port_forward(this_ip, this_port)
                    
                    status_obj["status"]["forwarding"]["available"] = True
                    status_obj["status"]["forwarding"]["phase"] = "Forwarded"
                    status_obj["status"]["forwarding"]["message"] = f"\"To IP {this_ip}\""
                else:
                    do_status_update = False
                                
            except Exception as e:
                print(f"> Error -> {str(e)}")
                
                status_obj["status"]["forwarding"]["available"]  = False
                status_obj["status"]["forwarding"]["phase"] = "Forwarding failed"
                status_obj["status"]["forwarding"]["message"] = f"Operator error: \"{str(e)}\""
            
            finally:
                # Update status obj
                if do_status_update:
                    if this_ip:
                        status_obj["status"]["forwarding"]["assignedIp"] = this_ip
                    
                    prismserver_api = client.resources.get(api_version="v1", kind="PrismServer")
                    prismserver_api.patch(
                        namespace="prism-servers",
                        name=this_prismserver_name,
                        body=status_obj,
                        content_type="application/merge-patch+json"
                    )
        
    except Exception as e:
        raise kopf.TemporaryError(f"FORWARDER: Error during supervision: {str(e)}")
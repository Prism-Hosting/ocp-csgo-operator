#!/usr/bin/python
"""
Operator to create and manage CS:GO servers.
"""

import time
import logging
import kopf
import traceback
from threading import Thread
from openshift.dynamic import DynamicClient
import modules.resources as resources
import modules.forwarder as forwarder
import modules.tcp_probe as probe
import modules.utils as utils

#  ------------------------
#           VARS
#  ------------------------
prism_object_initial_label_cache = {}
# { "prism_object": labels{} }
# Used for label_guard()

#  ------------------------
#         HANDLERS
#  ------------------------
# --- STARTUP ---
@kopf.on.startup()
def start_up(settings: kopf.OperatorSettings, logger, **kwargs):
    settings.posting.level = logging.ERROR
    settings.persistence.finalizer = 'prism-server-operator.prism-hosting.ch/kopf-finalizer'
    
    logger.info("Operator startup succeeded!")

@kopf.on.startup()
def launch_supervisor_loop(settings: None, logger, **kwargs):
    thread = Thread(target=supervisor_loop)
    thread.start()

# --- CREATE ---
@kopf.on.create('prism-hosting.ch', 'v1', 'prismservers')
def create(spec, meta, logger, **kwargs):
    """resource create handler"""

    logger.info("A resource is being created...")

    # Get resource metadata
    this_name = meta['name']
    namespace = meta['namespace']

    # Get resource data
    customer = spec['customer']
    sub_start = spec['subscriptionStart']
    env_vars = spec['env']
    
    # Sanity checks
    if not customer:
        raise kopf.PermanentError(f"Must set spec.customer")
    
    if not sub_start:
        logger.info(f"subscriptionStart not set, generating it instead. (Got {sub_start!r}).")
        sub_start = str( int( time.time() ) )
        logger.info(f"> subscriptionStart will now be: {sub_start}")

    # Fix bool'd env values
    for var in env_vars:
        if isinstance(var["value"], bool):
            offending_entry = var["name"]
            err_msg = f"A bool cannot be accepted here: spec.env['{offending_entry}']. Must be a string."

            utils.patch_resource(this_name, {'status': {'error': {'message': err_msg}}})
            
            raise kopf.PermanentError(err_msg)

    # Create server
    logger.info("Calling 'create_server'...")
    obj = create_server(logger, this_name, namespace, customer, sub_start, env_vars)

    logger.info("PRISM server created, updating labels...")

    # Patch labels of PrismResource
    labels_body = {
        "metadata": {
            "labels": { 
                'customer': obj.metadata.labels.customer,
                'name': obj.metadata.labels.name,
                'subscriptionStart': obj.metadata.labels.subscriptionStart,
                'custObjUuid': obj.metadata.labels.custObjUuid
            }
        }
    }
    
    # Update status
    utils.patch_resource(this_name, labels_body)

    return {
        'message': 'Successfully created',
        'time': f"{str( int( time.time() ) )}"
    }

# --- DELETE ---
@kopf.on.delete('prism-hosting.ch', 'v1', 'prismservers')
def clean_port_forward(spec: None, meta: None, status, logger, **kwargs):
    """
    Cleans a configured port forwarding of a service
    """
    
    ip = "Unknown IP"
    
    try:
        if status["forwarding"]["available"]:
            if not status["forwarding"]["assignedIp"]:
                return "No assignedIp yet"
                
            ip = status["forwarding"]["assignedIp"]
            
            logger.info(f"Triggering port forward deletion for: {ip}")
            forwarder.delete_port_forward_by_ip(ip)        
    except Exception as e:
        raise kopf.PermanentError(f"clean_port_forward() error: {str(e)}")

# --- UPDATES ---
@kopf.on.field('prism-hosting.ch', 'v1', 'prismservers', field='spec.env')
def update_env(new, meta, logger, **_):
    if not meta["labels"]["custObjUuid"]:
        raise kopf.TemporaryError("Resource does not yet have custObjUuid labels.")
    
    this_custObjUuid = meta["labels"]["custObjUuid"]
    customer = meta["labels"]["customer"]
    name = meta["name"]
    
    try:
        client = utils.kube_auth()
        api = client.resources.get(api_version="v1", kind="Deployment")
        deployments = api.get(namespace="prism-servers", label_selector=f"custObjUuid={this_custObjUuid}").items

        api = client.resources.get(api_version="v1", kind="Service")
        services = api.get(namespace="prism-servers", label_selector=f"custObjUuid={this_custObjUuid}").items
        
        if len(deployments) <= 0:
            raise kopf.PermanentError(f"Found no deployments for custObjUuid: {this_custObjUuid}")
        if len(deployments) > 1:
            raise kopf.PermanentError(f"Found too many deployments for custObjUuid: {this_custObjUuid}")
        # Existing deployment (meta)data
        deployment_name = deployments[0]["metadata"]["name"]
        port = services[0].spec.ports[0].port

        deployment_body = resources.get_deployment_body(logger, this_custObjUuid, name, "prism-servers", customer, port, meta["labels"], env_vars=new)
        
        patch_body = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": deployment_body["spec"]["template"]["spec"]["containers"]
                    }
                }
            }
        }
        
        utils.patch_resource(deployment_name, patch_body, kind="Deployment")

    except Exception as e:
        logger.warning(traceback.format_exc())
        raise kopf.PermanentError(f"Could not update env vars: {str(e)}")

@kopf.on.field('prism-hosting.ch', 'v1', 'prismservers', field='metadata.labels')
def label_guard(body, old, new, meta, logger, **_):
    """ Ensures that labels cannot get edited """
    
    expected_labels = [
        "custObjUuid",
        "customer",
        "name",
        "subscriptionStart"
    ]
    
    this_name = meta["name"]

    # Handle scenarios in which PrismServer was just labeled after creation
    if not old:
        return None
    else:
        # Create volatile record of initial labels for this PrismServer resource
        if not this_name in prism_object_initial_label_cache:
            prism_object_initial_label_cache[this_name] = old
    
    try:
        # Determine if certain labels changed
        patch_back = False
        if not all(label in new for label in expected_labels):
            logger.info("[i] Did not find expected labels for a PrismServer resource, patching back...")
            patch_back = True
            
        mismatched_labels = [key for key in prism_object_initial_label_cache[this_name] if key in new and prism_object_initial_label_cache[this_name][key] != new[key]]
        if len(mismatched_labels) > 0:
            logger.info(f"[i] Found NEW labels that are mismatched: {mismatched_labels}")
            patch_back = True
        
        # Actually do patching
        if patch_back:
            body = {'metadata': {'labels': prism_object_initial_label_cache[this_name]}}
            utils.patch_resource(this_name, body)
            kopf.warn(body, reason="LabelsImmutable", message="Certain labels may not be updated or removed.")
            
    except Exception as e:
        raise kopf.PermanentError(f"Label guard failed: {str(e)}")   
    
#  ------------------------
#          TIMERS
#  ------------------------
@kopf.timer('prism-hosting.ch', 'v1', 'prismservers', interval=3.0, initial_delay=20)
def monitor_service_port(stopped, meta, name, status, logger, **kwargs):
    """ Continuosly monitor the readiness of a CS:GO service and update the PrismServer object. """
    
    try:
        this_custObjUuid = meta["labels"]["custObjUuid"]
        
        # Test the service
        probe_verdict = False
        try:
            probe_verdict = probe.probe_service(this_custObjUuid)
        except Exception as e:  # Do not fatally exit, we want to ensure that status is False
            # Debug
            logger.warn(f"Exception calling probe_service(): {str(e)}")
        
        status_obj = {
            "status": {
                "tcpProbeResponding": probe_verdict
            }
        }
        
        # Only patch status if is not already as expected
        if not "tcpProbeResponding" in status or status["tcpProbeResponding"] != probe_verdict:
            logger.info(f"> Updating tcpProbeResponding (New: {probe_verdict}) for service with custObjUuid={this_custObjUuid}.")
            utils.patch_resource(name, status_obj)
        
    except Exception as e:
        logger.warn(f"monitor_service_port(): {str(e)}")

#  ------------------------
#         FUNCTIONS
#  ------------------------
def supervisor_loop():
    """ Port forwarder supervisor loop """
    
    while (True):
        try:
            forwarder.supervise_ips()
        except Exception as e:
            print(f"supervisor_loop() error: {str(e)}")
        
        time.sleep(3)

def create_server(logger, name, namespace, customer, sub_start, env_vars=None):
    """ Create the server """
    
    logger.info(f"Creating a resource in {namespace}")
    
    # Attempt logon
    dyn_client = utils.kube_auth()

    # Create the above schedule resource
    try:
        bodies = resources.get_resources(logger, name, namespace, customer, sub_start, env_vars)
    
        logger.info(f"Resource gathering finished, creating resources...")
        for body in bodies:
            # Owner reference
            kopf.adopt(body)
            
            resource = dyn_client.resources.get(api_version=body["apiVersion"], kind=body["kind"])
            
            logger.info(f"> Resource body: {body}")
            return_object = resource.create(body=body, namespace=namespace)
    except Exception as e:
        raise kopf.PermanentError(f"Resource creation has failed: {str(e)}")
    
    # CAUTION: Will be the LAST resource that was created
    return return_object

#!/usr/bin/python
"""
Operator to create and manage CS:GO servers.
"""

import time
import logging
import kopf
import kubernetes
import asyncio
from openshift.dynamic import DynamicClient
import modules.resources as resources
import modules.forwarder as forwarder

#  ------------------------
#         HANDLERS
#  ------------------------
@kopf.on.startup()
def start_up(settings: kopf.OperatorSettings, logger, **kwargs):
    settings.posting.level = logging.ERROR
    settings.persistence.finalizer = 'prism-server-operator.prism-hosting.ch/kopf-finalizer'
    
    logger.info("Operator startup succeeded!")

@kopf.on.startup()
async def supervisor_loop(settings: None, logger, **kwargs):
    # Launch async supervisor routine
    while (True):
        forwarder.supervise_ips()
        await asyncio.sleep(5)

@kopf.on.create('prism-hosting.ch', 'v1', 'prismservers')
def create_fn(spec, meta, logger, **kwargs):
    """resource create handler"""

    logger.info("A resource is being created...")

    # Get resource metadata
    name = meta.get('name')
    namespace = meta.get('namespace')

    # Get resource data
    customer = spec.get('customer')
    sub_start = spec.get('subscriptionStart')
    
    # Sanity checks
    if not customer:
        raise kopf.PermanentError(f"customer must be set. Got {customer!r}.")
    if not sub_start:
        logger.info(f"subscriptionStart not set, generating it instead. (Got {sub_start!r}).")
        sub_start = str( int( time.time() ) )
        logger.info(f"> subscriptionStart will now be: {sub_start}")

    # authenticate against the cluster
    logger.info("Doing logon for resource creation...")

    # Create server
    logger.info("Calling 'create_server'...")
    obj = create_server(logger, name, namespace, customer, sub_start)

    logger.info("PRISM server created.")

    return {'deployment': obj.metadata.name, "customer-objects-uuid": obj.metadata.labels.custObjUuid ,'message': 'Successfully created', 'time': f"{str( int( time.time() ) )}"}

#  ------------------------
#         FUNCTIONS
#  ------------------------
def create_server(logger, name, namespace, customer, sub_start):
    """
    Create the server
    """
    
    logger.info(f"Creating a resource in {namespace}")
    
    # Attempt logon
    try:
        kubernetes.config.load_incluster_config()
        k8s_client = kubernetes.client.ApiClient()
        dyn_client = DynamicClient(k8s_client)

    except Exception as e:
        raise kopf.PermanentError(f"Failed to create dynamic client: {str(e)}")

    # Create the above schedule resource
    try:
        bodies = resources.get_resources(logger, name, namespace, customer, sub_start)
    
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
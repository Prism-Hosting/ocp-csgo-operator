#!/usr/bin/python
"""
Operator to create and manage CS:GO servers.
"""

import datetime
import logging
import kopf
import kubernetes
from openshift.dynamic import DynamicClient
import uuid
import random
import yaml
import os

def allocate_random_port():
    """
    Allocate a random port to be used by a k8s service
    """
    
    # TODO: Get current ports, generate port, return if non-existent or retry ad infinitum.
    return random.randint(20000, 50000)

@kopf.on.startup()
def start_up(settings: kopf.OperatorSettings, logger, **kwargs):
    settings.posting.level = logging.ERROR
    settings.persistence.finalizer = 'prism-server-operator.prism-hosting.ch/kopf-finalizer'
    
    logger.info("Operator startup succeeded!")

def create_server(logger, name, namespace, customer, sub_start):
    """
    Create the server
    """
    
    logger.info(f"Creating a resource in {namespace}")
    
    # Attempt logon
    logger.info("> Attempting logon")
    try:
        kubernetes.config.load_incluster_config()
        k8s_client = kubernetes.client.ApiClient()
        dyn_client = DynamicClient(k8s_client)


    except Exception as e:
        raise kopf.PermanentError(f"Failed to create dynamic client: {str(e)}")
    
    logger.info("> dynamic client created")

    # Create the above schedule resource
    try:
        bodies = get_resources(logger, name, namespace, customer, sub_start)
    
        logger.info(f"Resource gathering finished, creating resources...")
        for body in bodies:
            logger.info(f"> Getting v1_server...")
            
            # BREAKS HERE (Handler 'create_fn' failed permanently: Resource creation has failed: name 'dyn_client' is not defined)
            v1_server = dyn_client.resources.get(api_version=body["apiVersion"], kind=body["kind"])
            
            logger.info(f"> Publishing resource...")
            return_object = v1_server.create(body=body, namespace=namespace)
    except Exception as e:
        raise kopf.PermanentError(f"Resource creation has failed: {str(e)}")
    
    return return_object

def get_resources(logger, name, namespace, customer, sub_start):
    """ Creates an array of kubernetes resources (Deployment, service) for further use

    Args:
        name (string): Name of server
        namespace (string): Namespace
        customer (string): Customer
        sub_start (string): DateTime of subscription start


    Returns:
        array: Array of resource objects
    """
    
    str_uuid = str(uuid.uuid4())
    uuid_part = str_uuid[:8]
    
    full_name = f"csgo-server-{name}-{customer}-{uuid_part}"
    
    labels = {
        'customer': customer,
        'name': full_name,
        'subscriptionStart': sub_start,
        'custObjUuid': str_uuid
    }
    
    try:
        resources = []
        resources.append(get_deployment_body(logger, str_uuid, name, namespace, customer, labels))
        resources.append(get_service_body(logger, str_uuid, name, namespace, customer, labels))
    except Exception as e:
        raise kopf.PermanentError(f"Was unable to generate all resources: {str(e)}")
    
    return resources

def get_deployment_body(logger, str_uuid, name, namespace, customer, labels):
    """ return deployment resource body

    Args:
        str_uuid (string): UUID as string
        name (string): Name of server
        namespace (string): Which namespace
        image (string): Which image
        customer (string): Which customer
        sub_start (string): When subscription has started
        labels (dict): Labels
    """
    
    uuid_part = str_uuid[:8]
    
    full_name = f"csgo-server-{name}-{customer}-{uuid_part}"
    secret_name = "gslt-code"
    
    # Todo: Import yaml and do things with it
    try:
        logger.info("Attempting to load deployment yaml...")
        path = os.path.join(os.path.dirname("resources/"), 'deployment.yaml')
        tmp_yaml = open(path, 'rt').read()
        
        logger.info("> Attempting to populate deployment yaml...")
        body = yaml.safe_load(
            tmp_yaml.format(
                full_name=full_name,
                namespace=namespace,
                labels=labels,
                customer=customer,
                sub_start=labels["subscriptionStart"],
                str_uuid=labels["custObjUuid"],
                secret_name=secret_name
            )
        )
        
        logger.info(f"> Populated deployment yaml: {body}")
    except Exception as e:
        raise kopf.PermanentError(f"Error during YAML population: {str(e)}.")
    
    return body

def get_service_body(logger, str_uuid, name, namespace, customer, labels):
    """ Generate service resource

    Args:
        str_uuid (string): UUID as string
        name (string): Name of server
        namespace (string): Which namespace
        customer (string): Which customer
        labels (dict): Labels
    """
    
    uuid_part = str_uuid[:8]
    full_name = f"csgo-server-{name}-{customer}-{uuid_part}"
    full_name = f"service-{full_name}"
    
    dyn_port = str(allocate_random_port())
    
    try:
        logger.info("Attempting to load service yaml...")
        path = os.path.join(os.path.dirname("resources/"), 'service.yaml')
        tmp_yaml = open(path, 'rt').read()
        
        logger.info("> Attempting to populate service yaml...")
        body = yaml.safe_load(
            tmp_yaml.format(
                full_name=full_name,
                customer=customer,
                sub_start=labels["subscriptionStart"],
                str_uuid=labels["custObjUuid"],
                namespace=namespace,
                labels=labels,
                dyn_port=dyn_port,
            )
        )
        
        logger.info(f"> Populated service yaml: {body}")
    except Exception as e:
        raise kopf.PermanentError(f"Error during YAML population: {str(e)}.")

    return body

@kopf.on.create('prism-hosting.ch', 'v1', 'prismservers')
def create_fn(spec, meta, logger, **kwargs):
    """resource create handler"""

    logger.info("A resource is being created...")

    # Get resource metadata
    name = meta.get('name')
    namespace = meta.get('namespace')

    # Get resource data
    customer = spec.get('customer')
    image = spec.get('image')
    sub_start = spec.get('subscriptionStart')
    
    # Sanity checks
    if not customer:
        raise kopf.PermanentError(f"customer must be set. Got {customer!r}.")
    if not image:
        raise kopf.PermanentError(f"image must be set. Got {image!r}.")
    if not sub_start:
        logger.info(f"subscriptionStart not set, generating it instead. (Got {sub_start!r}).")
        sub_start = str(int(datetime.now().timestamp()))
        logger.info(f("> subscriptionStart will now be: {sub_start}"))

    # authenticate against the cluster
    logger.info("Doing logon for resource creation...")

    # Create server
    logger.info("Calling 'create_server'...")
    obj = create_server(logger, name, namespace, customer, image, sub_start)

    logger.info("PRISM server created.")

    return {'server-name': obj.metadata.name, 'namespace': namespace, 'message': 'successfully created', 'time': f"{datetime.utcnow()}"}


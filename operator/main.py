#!/usr/bin/python
"""
Operator to create and manage CS:GO servers.
"""

import datetime
import logging
import kopf
from openshift.dynamic import DynamicClient
from kubernetes import client, config
import uuid
import random
import os

def allocate_random_port():
    """
    Allocate a random port to be used by a k8s service
    """
    
    # TODO: Get current ports, generate port, return if non-existent or retry ad infinitum.
    return random.randint(20000, 50000)

@kopf.on.startup()
def dyn_client_auth():
    """
    Authenticate dynamic client
    """
    config.load_incluster_config()
    k8s_config = client.Configuration()
    k8s_client = client.api_client.ApiClient(configuration=k8s_config)
    return DynamicClient(k8s_client)


def start_up(settings: kopf.OperatorSettings, logger, **kwargs):
    settings.posting.level = logging.ERROR
    settings.persistence.finalizer = 'prism-server-operator.prism-hosting.ch/kopf-finalizer'
    
    logger.info("Operator startup succeeded!")

def create_server(dyn_client, logger, name, namespace, customer, image, sub_start):
    """Create the velero.io/schedule object"""
    
    # TODO REWRITE
    v1_server = dyn_client.resources.get(api_version='velero.io/v1', kind='Pod')
    body = get_deployment_body(name, namespace, customer, image, sub_start)

    # Create the above schedule resource
    try:
        pod = v1_server.create(body=body, namespace=namespace)
    except Exception as err:
        logger.error(f"Creating server {namespace}-{name} failed with error: {err}")
        raise kopf.TemporaryError(f"Creating the server {namespace}-{name} in namespace {namespace} failed")

    return pod

def get_resources(name, namespace, customer, image, sub_start):
    """ Creates an array of kubernetes resources (Deployment, service) for further use

    Args:
        name (string): Name of server
        namespace (string): Namespace
        customer (string): Customer
        image (string): Image to use
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
        resources.append(get_deployment_body(str_uuid, name, namespace, customer, image, sub_start, labels))
    except Exception as e:
        raise kopf.TemporaryError(f"Was unable to obtain all resources: {str(e)}")
    
    return resources

def get_deployment_body(str_uuid, name, namespace, customer, image, sub_start, labels):
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
    
    body = {
        'apiVersion': 'v1',
        'kind': 'Deployment',
        'metadata': {
            'name': full_name,
            'namespace': namespace,
            'labels': labels
        },
        'spec': {
            "selector": {
                "matchLabels": {
                    'customer': customer,
                    "name": full_name                    
                }              
            },
            "template": {
                "metadata": {
                    "labels": {
                        'customer': customer,
                        'name': full_name,
                        'subscriptionStart': sub_start,
                        'custObjUuid': str_uuid
                    }
                },
                "spec": {
                    "containers": [
                        {
                            "name": full_name,
                            "image": image,
                            'ports': [ {'containerPort': 27015 } ],
                            'env': [
                                {
                                    "name": "CSGO_GSLT",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": secret_name,
                                            "key": "value"
                                        }
                                    } 
                                }
                            ]
                        }
                    ]
                }
            }
        }
    }
    
    return body

def get_service_body(str_uuid, name, namespace, customer, sub_start, labels):
    """ Generate service resource

    Args:
        str_uuid (string): UUID as string
        name (string): Name of server
        namespace (string): Which namespace
        customer (string): Which customer
        sub_start (int): When subscription for started
        labels (dict): Labels
    """
    
    uuid_part = str_uuid[:8]
    full_name = f"csgo-server-{name}-{customer}-{uuid_part}"
    
    dyn_port = str(allocate_random_port())
    
    # !!!!!!!!!!!!!!!!!
    # TODO: Dynamic port allocation
    # !!!!!!!!!!!!!!!!!
    
    body = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {
            'name': f"service-{full_name}",
            'namespace': namespace,
            'labels': labels 
        },
        'spec': {
            "selector": {
                'custObjUuid': str_uuid
            },
            "ports": [
                {
                    "name": "ingress-tcp",
                    "port": 27015,
                    "protocol": "TCP",
                    "targetPort": dyn_port
                },
                {
                    "name": "ingress-udp",
                    "port": 27015,
                    "protocol": "UDP",
                    "targetPort": dyn_port
                },
            ],
            "type": "LoadBalancer"
        }
    }
            
    return body
    

@kopf.on.create('prism-hosting.ch', 'v1', 'prismservers')
def create_fn(spec, meta, logger, **kwargs):
    """resource create handler"""

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
        raise kopf.PermanentError(f"sub_start must be set. Got {sub_start!r}.")


    # authenticate against the cluster
    dyn_client = dyn_client_auth()

    # Create server
    obj = create_server(dyn_client, logger, name, namespace, image, sub_start)

    logger.info(f"PRISM Server created: {obj}")

    return {'server-name': obj.metadata.name, 'namespace': namespace, 'message': 'successfully created', 'time': f"{datetime.utcnow()}"}


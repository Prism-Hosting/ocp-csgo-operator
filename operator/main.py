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
import os

@kopf.on.startup()
def dyn_client_auth():
    """ensure the api authentication
    for the dynamic-client, piggibacked
    on kopf"""
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
    
    v1_server = dyn_client.resources.get(api_version='velero.io/v1', kind='Pod')
    body = get_pod_body(name, namespace, customer, image, sub_start)

    # Create the above schedule resource
    try:
        pod = v1_server.create(body=body, namespace=namespace)
    except Exception as err:
        logger.error(f"Creating server {namespace}-{name} failed with error: {err}")
        raise kopf.TemporaryError(f"Creating the server {namespace}-{name} in namespace {namespace} failed")

    return pod

def get_pod_body(name, namespace, customer, image, sub_start):
    """ return pod resource body

    Args:
        name (string): _description_
        namespace (string): Which namespace
        customer (string): Which customer
        sub_start (string): When subscription for started
    """
    
    obj_uuid = uuid.uuid4()
    uuid_part = str(uuid)[:8]
    uuid_full = str(obj_uuid)
    
    full_name = f"csgo-server-{name}-{customer}-{uuid_part}"
    secret_name = "gslt-code"
    
    body = {
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {
            'name': full_name,
            'namespace': namespace,
            'labels': {
                'customer': customer,
                'name': full_name,
                'subscriptionStart': sub_start,
                'objUuid': uuid_full
            }
        },
        'spec': {
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


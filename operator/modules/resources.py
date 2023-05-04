"""
Module to load, transform and return kubernetes resources
"""

import random
import yaml
import uuid
import kopf
import os

def allocate_random_port():
    """
    Allocate a random port to be used by a k8s service
    """
    
    # TODO: Get current ports, generate port, return if non-existent or retry ad infinitum.
    return random.randint(20000, 50000)

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

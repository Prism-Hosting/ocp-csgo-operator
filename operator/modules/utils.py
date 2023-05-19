"""
General utilities
"""

from openshift.dynamic import DynamicClient
import kubernetes
import kopf
import uuid

def kube_auth():
    """ Authenticate against an oc cluster """
    
    try:
        kubernetes.config.load_incluster_config()
        k8s_client = kubernetes.client.ApiClient()
        return DynamicClient(k8s_client)

    except Exception as e:
        raise kopf.PermanentError(f"Failed to create dynamic client: {str(e)}")
    
def patch_resource(name, body, kind="PrismServer", namespace="prism-servers", content_type="application/merge-patch+json"):
    """ Patch a kubernetes resource, defaults to "PrismServer"

    Args:
        name (string): Name of the kubernetes resource (meta.name)
        body (dict): Body to patch resource with
        kind (string): Resource kind
        namespace (string): Namespace of the resource
        content_type (string): Content type to use for patching operation
    """
    
    client = kube_auth()
    
    prismserver_api = client.resources.get(api_version="v1", kind=kind)
    prismserver_api.patch(
        namespace=namespace,
        name=name,
        body=body,
        content_type=content_type
    )

def is_uuid(value):
    """ Validate if argument is an UUID """
    
    try:
        uuid.UUID(str(value))

        return True
    except ValueError:
        return False
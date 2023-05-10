"""
General utilities
"""

from openshift.dynamic import DynamicClient
import kubernetes
import kopf

def kube_auth():
    try:
        kubernetes.config.load_incluster_config()
        k8s_client = kubernetes.client.ApiClient()
        return DynamicClient(k8s_client)

    except Exception as e:
        raise kopf.PermanentError(f"Failed to create dynamic client: {str(e)}")
    
def patch_resource(resource_name, body):
    """_summary_

    Args:
        resource_name (string): Name of the PrismServer resource (meta.name)
        body (dict): Body to patch resource with
    """
    
    client = kube_auth()
    
    prismserver_api = client.resources.get(api_version="v1", kind="PrismServer")
    prismserver_api.patch(
        namespace="prism-servers",
        name=resource_name,
        body=body,
        content_type="application/merge-patch+json"
    )
#!/bin/bash
if [ -z ${ENV_NAMESPACE} ]; then
    echo "[i] Not running namespaced"
    kopf run main.py --verbose --all-namespaces
else
    echo "[i] Running in namespace: $ENV_NAMESPACE"
    kopf run main.py --verbose --namespace $ENV_NAMESPACE
fi
#!/bin/bash
echo [i] Running in namespace: $ENV_NAMESPACE
kopf run main.py --verbose --namespace $ENV_NAMESPACE
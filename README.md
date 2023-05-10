# ocp-csgo-operator
Operator to facilitate the creation and management of CS:GO servers.

## Usage
Create a `PrismServer` resource with at least the `.spec.customer` field populated.  
Optionally, a UNIX timestamp can be inserted into the `.spec.subscriptionStart` field.

Once such a resource has been created, the operator will create the following:
- Deployment
- Service
- PersistentVolumeClaim

**Note:** It is possible for one customer to have multiple `PrismServer` objects as they all obtain a unique UUID shared among all its resources later on.

The names of these resources is based on the name of the `PrismServer` object and, generally, follows this syntax:
```bash
csgo-server-{name}-{customer}-{uuid-part}
```

**Note:** The `PrismServer` object serves as a global owner of all the resources.* 
Deleting it will also delete all other resources that were created thanks to it.

If the creation of all these resources has successfully finished, the `status` field of the `PrismServer` object will be updated:
```yaml
status:
  create_fn:
    customer-objects-uuid: 2de09f00-0ec9-4d33-993a-8b884173d199
    message: Successfully created
    server-name: service-csgo-server-prismserver-test-obj-cust-01-2de09f00
    time: '1683220281'
```

Every resource has the following labels:
```yaml
custObjUuid: 2de09f00-0ec9-4d33-993a-8b884173d199
# UUID of the PrismServer object

customer: cust-01
# Customer

name: csgo-server-prismserver-test-obj-cust-01-2de09f00
# Full name of resource

subscriptionStart: '1683139792'
# Start of the subscription
```

To view an example of a `PrismServer` resource, look at the `test` folder in this repo.

#### Quick testing

``` shell
REPO=prismhosting

docker build -t $REPO/ocp-csgo-operator:latest .
docker image push $REPO/ocp-csgo-operator:latest

# Destroy ALL prism resources
oc -n prism-servers delete (oc -n prism-servers get prismserver -o name)
oc -n prism-servers delete (oc -n prism-servers get deployment --selector='custObjUuid' -o name)
oc -n prism-servers delete (oc -n prism-servers get service --selector='custObjUuid' -o name)

# Destroy operator pods
oc -n prism-servers delete (oc -n prism-servers get po --selector=app=prismserver-operator -o name)

oc apply -f test/prismserver_example.yaml
```
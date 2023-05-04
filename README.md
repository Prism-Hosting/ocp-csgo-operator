# ocp-csgo-operator
Operator to facilitate creation and management of cs:go servers

## Usage
For an example yaml, see the folder `test`.

### Quick testing

``` shell
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
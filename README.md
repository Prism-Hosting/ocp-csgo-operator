# ocp-csgo-operator
Operator to facilitate creation and management of cs:go servers

## Usage
For an example yaml, see the folder `test`.

## Custom building
Proper building and tagging:

``` shell
docker build -t thisisnttheway/ocp-csgo-operator:latest .
docker image push thisisnttheway/ocp-csgo-operator:latest
```
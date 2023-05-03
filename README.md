# ocp-csgo-operator
Operator to facilitate creation and management of cs:go servers

## Usage
Create server:
```yaml
apiVersion: prismservers.prism-hosting.ch/v1
kind: PrismServer
spec:
  customer: cust-01
  # [string] Customer identifier

  image: timche/csgo
  # [string] Docker image

  subscriptionStart: 1683139792
  # [string] UNIX timestamp
```
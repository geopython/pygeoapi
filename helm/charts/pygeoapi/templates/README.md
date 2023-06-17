# Access Application

- [Access Application](#access-application)
    - [List Service Name](#list-service-name)
    - [List Pod Name](#list-pod-name)
- [Connection Types](#connection-types)
  - [NodePort](#nodeport)
  - [LoadBalancer](#loadbalancer)
  - [ClusterIP](#clusterip)
    - [ClusterIP Example](#clusterip-example)
- [Visit Application](#visit-application)

Variables: 
- Release.Namespace : the k8s namespace pygeoapi is deployed to
- pygeoapi-helm.fullname : values.fullnameOverride variable

### List Service Name

```bash
kubectl get svc --namespace Release.Namespace
```

### List Pod Name

```bash
kubectl get pods --namespace Release.Namespace
```

# Connection Types

Get the application URL by running these commands:

## NodePort

```bash
export NODE_PORT=$(kubectl get --namespace {{ .Release.Namespace }} -o jsonpath="{.spec.ports[0].nodePort}" services {{ include "pygeoapi-helm.fullname" . }})

export NODE_IP=$(kubectl get nodes --namespace {{ .Release.Namespace }} -o jsonpath="{.items[0].status.addresses[0].address}")

echo http://$NODE_IP:$NODE_PORT
```

## LoadBalancer

NOTE: It may take a few minutes for the LoadBalancer IP to be available.

You can watch the status of the svc by running:

```bash
kubectl get --namespace {{ .Release.Namespace }} svc -w {{ include "pygeoapi-helm.fullname" . }}
```

When running and IP provisoined, user the following command to get URL:

```bash
export SERVICE_IP=$(kubectl get svc --namespace {{ .Release.Namespace }} {{ include "pygeoapi-helm.fullname" . }} --template "{{"{{ range (index .status.loadBalancer.ingress 0) }}{{.}} "}}"
```

## ClusterIP

```bash
export POD_NAME=$(kubectl get pods --namespace {{ .Release.Namespace }} -l "app.kubernetes.io/name={{ include "pygeoapi-helm.name" . }},app.kubernetes.io/instance="pygeoapi-helm.name" -o jsonpath="{.items[0].metadata.name}")
```

```bash
export CONTAINER_PORT=$(kubectl get pod --namespace {{ .Release.Namespace }} $POD_NAME -o jsonpath="{.spec.containers[0].ports[0].containerPort}")
```

### ClusterIP Example

.Release.Namespace = pygeoapi
pygeoapi-helm.name = pygeoapi

```bash
kubectl get pods --namespace pygeoapi -l "app.kubernetes.io/name=pygeoapi,app.kubernetes.io/instance=pygeoapi" -o jsonpath="{.items[0].metadata.name}"
```

# Visit Application

```bash
echo "Visit http://127.0.0.1:8080 to use your application"
kubectl --namespace {{ .Release.Namespace }} port-forward $POD_NAME 8080:$CONTAINER_PORT
```
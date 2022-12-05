# Kubernetes `pygeoapi` Helm Chart

A basic set of manifests to generate a Helm Chart to deploy pygeoapi
on a Kubernetes Cluster. 

- [Kubernetes `pygeoapi` Helm Chart](#kubernetes-pygeoapi-helm-chart)
  - [Creating The Chart](#creating-the-chart)
  - [Push Chart to Repository](#push-chart-to-repository)
  - [Deploy Chart to Kubernetes](#deploy-chart-to-kubernetes)
  - [Deployment Configuration](#deployment-configuration)

## Creating The Chart

```bash
helm package charts/pygeoapi
```

## Push Chart to Repository

```bash
helm push <HELM_TGZ> oci://<container-registry-URL>/helm
```

## Deploy Chart to Kubernetes

```bash
helm install pygeoapi oci://<container-registry-URL>/helm --version 0.1.0 --namespace <namespace> --values values.yaml
```

## Deployment Configuration

- Service
  - Make deployment accessible to Ingress and/or other services
- Deployment
  - Maps Configmap to server configuration
- Configmap
  - Holds the contents of the server `local.config.yml` configuration
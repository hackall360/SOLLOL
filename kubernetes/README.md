# SOLLOL Kubernetes Deployment

Production-ready Kubernetes manifests for deploying SOLLOL with Ollama nodes.

## Architecture

```
┌─────────────────────────────────────────────────┐
│           LoadBalancer / Ingress                │
│         sollol-gateway-external:8000             │
└────────────────────┬────────────────────────────┘
                     │
          ┌──────────▼─────────────┐
          │   SOLLOL Gateway Pod   │
          │   (sollol-gateway)     │
          │   - Port 8000 (API)    │
          │   - Port 9090 (metrics)│
          └──────────┬─────────────┘
                     │
      ┌──────────────┼──────────────┐
      │              │              │
┌─────▼────┐  ┌─────▼────┐  ┌─────▼────┐
│ Ollama   │  │ Ollama   │  │ Ollama   │
│ Node 0   │  │ Node 1   │  │ Node 2   │
│ + GPU    │  │ + GPU    │  │ + GPU    │
└──────────┘  └──────────┘  └──────────┘
```

## Prerequisites

1. **Kubernetes cluster** (v1.20+) with:
   - GPU nodes with NVIDIA GPU Operator installed
   - StorageClass for persistent volumes
   - LoadBalancer support (or Ingress controller)

2. **kubectl** configured and connected to your cluster

3. **GPU Support** (optional but recommended):
   ```bash
   # Install NVIDIA GPU Operator
   helm install --wait --generate-name \
     -n gpu-operator --create-namespace \
     nvidia/gpu-operator
   ```

## Quick Start

### 1. Deploy Namespace and Ollama Nodes

```bash
# Create namespace and deploy Ollama StatefulSet
kubectl apply -f kubernetes/ollama-nodes.yaml

# Wait for Ollama pods to be ready
kubectl wait --for=condition=ready pod -l app=ollama-node -n sollol --timeout=300s

# Check Ollama pods
kubectl get pods -n sollol
```

### 2. Deploy SOLLOL Gateway

```bash
# Deploy gateway and services
kubectl apply -f kubernetes/sollol-gateway.yaml

# Wait for gateway to be ready
kubectl wait --for=condition=ready pod -l app=sollol-gateway -n sollol --timeout=180s

# Get external IP
kubectl get svc sollol-gateway-external -n sollol
```

### 3. Verify Deployment

```bash
# Port-forward to test locally
kubectl port-forward -n sollol svc/sollol-gateway 8000:8000

# Test health endpoint
curl http://localhost:8000/health

# Test chat endpoint
curl http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Configuration

### Scaling Ollama Nodes

```bash
# Scale to 5 nodes
kubectl scale statefulset ollama-node -n sollol --replicas=5

# Update config map with new nodes
kubectl edit configmap sollol-config -n sollol
```

### Resource Limits

Edit resource requests/limits in the manifests:

```yaml
resources:
  requests:
    memory: "4Gi"
    cpu: "2000m"
    nvidia.com/gpu: "1"
  limits:
    memory: "16Gi"
    cpu: "4000m"
    nvidia.com/gpu: "1"
```

### GPU Node Selection

If your cluster has specific GPU node pools:

```yaml
nodeSelector:
  cloud.google.com/gke-accelerator: nvidia-tesla-t4
  # or
  node.kubernetes.io/instance-type: g4dn.xlarge
```

## Monitoring

### Check Gateway Health

```bash
kubectl get pods -n sollol -l app=sollol-gateway
kubectl logs -n sollol -l app=sollol-gateway --tail=50
```

### Check Ollama Nodes

```bash
kubectl get pods -n sollol -l app=ollama-node
kubectl logs -n sollol ollama-node-0 --tail=50
```

### Access Metrics

```bash
# Port-forward Prometheus metrics
kubectl port-forward -n sollol svc/sollol-gateway 9090:9090

# Scrape metrics
curl http://localhost:9090/metrics
```

## Troubleshooting

### Pods Not Starting

```bash
# Check events
kubectl get events -n sollol --sort-by='.lastTimestamp'

# Describe pod
kubectl describe pod -n sollol <pod-name>

# Check logs
kubectl logs -n sollol <pod-name> --previous
```

### GPU Not Available

```bash
# Verify GPU operator
kubectl get pods -n gpu-operator

# Check node GPU capacity
kubectl get nodes -o json | jq '.items[].status.capacity'
```

### Out of Storage

```bash
# Check PVCs
kubectl get pvc -n sollol

# Increase storage (edit PVC)
kubectl edit pvc ollama-data-ollama-node-0 -n sollol
```

## Production Considerations

### High Availability

For production, scale the gateway:

```yaml
spec:
  replicas: 3  # Multiple gateway replicas
```

### Ingress

Replace LoadBalancer with Ingress:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: sollol-ingress
  namespace: sollol
spec:
  rules:
  - host: sollol.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: sollol-gateway
            port:
              number: 8000
```

### Model Preloading

Add init container to pull models on pod startup:

```yaml
initContainers:
- name: model-loader
  image: ollama/ollama:latest
  command: ["/bin/sh", "-c"]
  args:
    - |
      ollama pull llama3.2
      ollama pull mistral
```

### Persistent Metrics

Deploy Prometheus/Grafana stack:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
```

## Cleanup

```bash
# Delete all SOLLOL resources
kubectl delete -f kubernetes/

# Delete namespace
kubectl delete namespace sollol
```

## Cost Optimization

- **GPU Nodes:** Use spot/preemptible instances for dev/test
- **Autoscaling:** Use cluster autoscaler to scale nodes based on demand
- **Storage:** Use cheaper storage classes for non-production

## Next Steps

- Set up **Horizontal Pod Autoscaling** based on request rate
- Configure **PodDisruptionBudgets** for high availability
- Implement **NetworkPolicies** for security
- Add **ServiceMonitor** for Prometheus integration

# Besu QBFT on Kubernetes (5 Validators + 1 RPC)

This repository now targets:
- 5 QBFT validators: `validator1`..`validator5`
- 1 non-validator RPC node: `rpc-node`
- Persistent volumes: `90Gi` per node (`storageClassName: blockchain-local`)
- Namespace: `blockchain`

## Prerequisites

- Kubernetes cluster with at least 6 bindable PVs of `>=90Gi` in `blockchain-local`
- `kubectl` access to your cluster
- Keys present in:
  - `keys/validator1/key` ... `keys/validator5/key`
  - `keys/rpc-node/key`

## Regenerate Chain Artifacts

Run from repo root whenever keys or validator set changes:

```bash
python3 scripts/generate-genesis.py
python3 scripts/generate-enodes.py
```

Then ensure `k8s/config/configmap-genesis.yaml` uses the generated `extraData` (already patched in this repo).

## Deploy

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/config/configmap-genesis.yaml
kubectl apply -f k8s/config/besu-static-nodes-configmap.yaml
kubectl apply -f k8s/secrets/
kubectl apply -f k8s/validators/validator1.yaml
kubectl apply -f k8s/validators/validator2.yaml
kubectl apply -f k8s/validators/validator3.yaml
kubectl apply -f k8s/validators/validator4.yaml
kubectl apply -f k8s/validators/validator5.yaml
kubectl apply -f k8s/rpc/deployment.yaml
kubectl apply -f k8s/rpc/service.yaml
```

## Validate

```bash
kubectl get pods -n blockchain -w
kubectl logs -n blockchain statefulset/validator1 --tail=200
kubectl logs -n blockchain statefulset/rpc-node --tail=200
```

Check peer count from RPC:

```bash
RPC_POD=$(kubectl get pod -n blockchain -l app=rpc-node -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n blockchain "$RPC_POD" -- \
  curl -s -X POST http://127.0.0.1:8545 \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":1}'
```

## Important: When Genesis/Validator Set Changes

You must wipe old chain data (PVCs), otherwise pods will loop with genesis mismatch.

```bash
kubectl delete statefulset -n blockchain validator1 validator2 validator3 validator4 validator5 rpc-node
kubectl get pvc -n blockchain -o name | \
  grep -E 'data-(validator[1-5]|rpc-node)-0' | \
  xargs -r kubectl delete -n blockchain
```

If your PVCs are not label-selectable, list and delete manually:

```bash
kubectl get pvc -n blockchain
kubectl delete pvc -n blockchain <pvc-name>
```

Then run the Deploy section again.

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
kubectl apply -f k8s/config/besu-startup-configmap.yaml
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

Wait for workloads:

```bash
kubectl rollout status statefulset/validator1 -n blockchain
kubectl rollout status statefulset/validator2 -n blockchain
kubectl rollout status statefulset/validator3 -n blockchain
kubectl rollout status statefulset/validator4 -n blockchain
kubectl rollout status statefulset/validator5 -n blockchain
kubectl rollout status statefulset/rpc-node -n blockchain
```

## Health Check Guide

Use this checklist whenever you deploy/restart.

1. Pod health and restarts:

```bash
kubectl get pods -n blockchain -o wide
```

Expected:
- all 6 pods `2/2 Running`
- restarts stable (not continuously increasing)

2. Open local RPC tunnel:

```bash
kubectl port-forward -n blockchain svc/rpc-node 8545:8545
```

In another terminal:

3. Peer count growth/stability:

```bash
curl -s -X POST http://127.0.0.1:8545 \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":1}'
```

Expected:
- typically `0x4` or `0x5` in this topology

4. Block production (run twice with ~10 seconds gap):

```bash
curl -s -X POST http://127.0.0.1:8545 \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":2}'
```

Expected:
- block number increases over time

5. Validator visibility:

```bash
curl -s -X POST http://127.0.0.1:8545 \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"qbft_getValidatorsByBlockNumber","params":["latest"],"id":3}'
```

Expected:
- returns 5 validator addresses

6. Connected peer details (optional deep check):

```bash
curl -s -X POST http://127.0.0.1:8545 \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"admin_peers","params":[],"id":4}'
```

Expected:
- non-empty array with enodes and remote addresses

## Interact With The Network

With port-forward still active:

1. Chain ID:

```bash
curl -s -X POST http://127.0.0.1:8545 \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":10}'
```

2. Latest full block:

```bash
curl -s -X POST http://127.0.0.1:8545 \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["latest",true],"id":11}'
```

3. Balance of an address:

```bash
curl -s -X POST http://127.0.0.1:8545 \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0x0000000000000000000000000000000000000000","latest"],"id":12}'
```

4. Send a signed raw transaction:

```bash
curl -s -X POST http://127.0.0.1:8545 \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_sendRawTransaction","params":["0x<signed_tx_hex>"],"id":13}'
```

Notes:
- This setup does not expose personal account management APIs.
- Send transactions as externally signed raw payloads (`eth_sendRawTransaction`).

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

## Fast Troubleshooting

1. Pods crash with `Option '--p2p-host' should be specified only once`.
- Check manifests do not include duplicate `--p2p-host` in args and startup script at the same time.

2. Pods are healthy but no blocks (`eth_blockNumber` stuck) and `net_peerCount` is `0x0`.
- Check `admin_peers` is empty or not.
- Check startup script/ConfigMap was applied: `kubectl apply -f k8s/config/besu-startup-configmap.yaml`.
- Restart pods after config updates:

```bash
kubectl delete pod -n blockchain validator1-0 validator2-0 validator3-0 validator4-0 validator5-0 rpc-node-0
```

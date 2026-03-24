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

## Block Explorer (Optional)

This deploys a Blockscout UI backed by an ephemeral Postgres (no PV). Data resets on pod restart. DB migrations run automatically on startup.

1. Set a real `SECRET_KEY_BASE`:

```bash
openssl rand -hex 32
```

Put the output in `k8s/blockexplorer/blockscout.yaml` at `SECRET_KEY_BASE`.

2. Deploy:

```bash
kubectl apply -f k8s/blockexplorer/postgres.yaml
kubectl apply -f k8s/blockexplorer/blockscout.yaml
```

3. Access the UI:

```bash
kubectl port-forward -n blockchain svc/blockscout 4000:80
```

Open `http://127.0.0.1:4000` in a browser.

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

### Latest Verified Health Snapshot

Recorded on 2026-03-23 17:10 UTC after restoring full peer mesh.

- Block height: `0x7` (7) and advancing
- Peer count: `0x5` on `rpc-node` and all validators

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

## Permanent Access (Ingress + NodePort)

This setup exposes UIs through the Istio ingress gateway (HTTP NodePort) and exposes Besu RPC through a NodePort service.

Current NodePort values:
- Istio ingress HTTP: `32037` (from `istio-system/istio-ingressgateway`)
- RPC HTTP: `30545` and WS: `30546` (from `blockchain/rpc-node-external`)
- RPC HTTPS (nginx): `31933` (from `blockchain/rpc-nginx`)
- Kubernetes Dashboard: `30443` (from `kubernetes-dashboard/kubernetes-dashboard-nodeport`)

Example node IP used below: `83.212.80.192`

UI URLs (via Istio ingress gateway):
- Kiali: `http://kiali.83.212.80.192.nip.io:32037`
- Grafana: `http://grafana.83.212.80.192.nip.io:32037`
- Prometheus: `http://prometheus.83.212.80.192.nip.io:32037`
- Blockscout: `http://blockscout.83.212.80.192.nip.io:32037`

Kubernetes Dashboard (NodePort HTTPS):
- `https://83.212.80.192:30443`

RPC endpoints:
- HTTPS (standard): `https://snf-83472.ok-kno.grnetcloud.net/rpc`
- HTTP: `http://83.212.80.192:30545`
- HTTPS (nginx): `https://snf-83472.ok-kno.grnetcloud.net:31933/rpc`
- WS: `ws://83.212.80.192:30546`

MetaMask network fields:
- Network Name: `besu-qbft`
- RPC URL: `https://snf-83472.ok-kno.grnetcloud.net/rpc`
- Chain ID: `1337`
- Currency Symbol: `ETH`
- Block Explorer URL: `https://snf-83472.ok-kno.grnetcloud.net/blockscout/`

Prefunded accounts (genesis alloc):
- Generated in `genesis/prefunded-accounts.json`
- Each has `100 ETH` balance
- Treat these keys as test-only and rotate for production

If you want to use a different node IP, replace `83.212.80.192` everywhere above and keep the same ports.

## Observability (Grafana, Prometheus, Alertmanager)

Besu exposes Prometheus metrics on port `9545`. This repo installs:
- ServiceMonitor: `k8s/monitoring/servicemonitor-besu.yaml`
- Grafana dashboards: `k8s/monitoring/grafana-dashboard-besu.yaml` and `k8s/monitoring/grafana-dashboard-besu-validators.yaml`
- Alert rules: `k8s/monitoring/prometheus-rule-besu.yaml`

### Quick Access (Port-Forward)

Grafana:
```bash
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80
```
Prometheus:
```bash
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090
```
Alertmanager:
```bash
kubectl -n monitoring port-forward svc/alertmanager-monitoring-kube-prometheus-alertmanager 9093:9093
```

### Grafana Dashboards

Look for these dashboards:
- `Besu QBFT Overview`
- `Besu QBFT Validators`

### Prometheus Queries

Block height:
```promql
ethereum_blockchain_height
```
Peer count:
```promql
sum by (service) (besu_peers_peer_count_by_client{client="Besu"})
```
RPC error rate (non BLOCK_NOT_FOUND):
```promql
sum by (service) (rate(besu_rpc_errors_count_total{errorType!="BLOCK_NOT_FOUND"}[5m]))
```

### Alert Rules Installed

These are loaded in Prometheus under the `besu.rules` group:
- `BesuPeerCountLow` (peer count < 3 for 5m)
- `BesuBlockStalled` (rpc-node block height not advancing for 5m)
- `BesuRpcErrorsHigh` (non BLOCK_NOT_FOUND errors > 1 req/s for 5m)
- `BesuNoPeersAndNoBlocks` (zero peers and no block growth for 5m)

### Alertmanager Validation

1. Open Alertmanager UI:
```bash
kubectl -n monitoring port-forward svc/alertmanager-monitoring-kube-prometheus-alertmanager 9093:9093
```

2. Visit:
```
http://127.0.0.1:9093
```

3. Verify alerts from `besu.rules` appear when conditions are met.

### Observability Troubleshooting

1. Metrics not showing in Prometheus targets:
```bash
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090
```
Open `http://127.0.0.1:9090/targets` and check that `rpc-node` + `validator1..5` targets are `UP`.

2. Grafana dashboards not appearing:
- Confirm the dashboard ConfigMaps exist and are labeled `grafana_dashboard: "1"`:
```bash
kubectl -n monitoring get configmap | grep grafana-dashboard-besu
```

3. Prometheus rules not loaded:
```bash
kubectl -n monitoring exec prometheus-monitoring-kube-prometheus-prometheus-0 -c prometheus -- \
  wget -qO- http://127.0.0.1:9090/api/v1/rules | head -c 400
```
Look for the `besu.rules` group.

### Alert Testing (Temporary)

To validate Alertmanager notifications end-to-end, you can temporarily lower thresholds for a few minutes and then revert.

Example (edit `k8s/monitoring/prometheus-rule-besu.yaml`):
- Set `BesuPeerCountLow` threshold to `< 10`
- Set `BesuBlockStalled` lookback to `[1m]` and `for: 1m`

Apply, confirm alerts in Alertmanager, then restore the original values.

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

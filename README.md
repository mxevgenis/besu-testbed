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

Recorded on 2026-04-23 14:28 UTC after recovering `worker2` and restoring peer discovery.

- Block height: `0x37154` and advancing
- Peer count: `0x5` on `rpc-node` and validators
- Blockscout HTTP check: `200 OK`

## Troubleshooting

Use this section when Blockscout is stale, block height is not advancing, or some Besu pods are stuck after a node reboot/outage.

### 1. Check cluster and blockchain status

```bash
kubectl get nodes -o wide
kubectl get pods -n blockchain -o wide
kubectl get pvc -n blockchain -o wide
```

What to look for:
- a Kubernetes worker in `NotReady`
- Besu pods stuck in `Terminating`
- PVCs bound to local PVs on the failed node

If a node is powered off and the blockchain PVs are local to that node, those pods cannot be moved elsewhere with their existing data. Recover the node first if possible.

### 2. If a worker is down, recover the node first

Typical symptoms:
- `kubectl describe node <node>` shows `Kubelet stopped posting node status`
- SSH to the worker fails
- affected Besu pods sit on that worker in `Terminating`

If the VM is hard powered off at the cloud provider, bring it back there first. Once the node returns as `Ready`, Kubernetes can reuse the existing local disks and recreate the StatefulSet pods on that node.

### 3. Verify blockchain health after the node returns

```bash
kubectl get pods -n blockchain -o wide
kubectl exec -n blockchain blockscout-<pod> -c blockscout -- sh -lc \
  'curl -s -X POST http://rpc-node:8545 -H "Content-Type: application/json" \
  --data "{\"jsonrpc\":\"2.0\",\"method\":\"net_peerCount\",\"params\":[],\"id\":1}"'
kubectl exec -n blockchain blockscout-<pod> -c blockscout -- sh -lc \
  'curl -s -X POST http://rpc-node:8545 -H "Content-Type: application/json" \
  --data "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":2}"'
```

Healthy signs:
- all six Besu pods become `2/2 Running`
- `net_peerCount` returns about `0x5`
- `eth_blockNumber` increases over time

### 4. If pods are running but block production is stalled

This can happen after a cold restart if Besu rebuilt `/data/static-nodes.json` before all pod DNS records were resolvable.

Symptoms:
- pods are `Running`, but block height does not change
- `net_peerCount` is `0x0` or `0x1`
- `admin_peers` shows only a partial mesh
- `/data/static-nodes.json` inside a pod contains only itself or one peer

Check it with:

```bash
kubectl exec -n blockchain validator1-0 -c besu -- cat /data/static-nodes.json
kubectl exec -n blockchain blockscout-<pod> -c blockscout -- sh -lc \
  'curl -s -X POST http://validator2:8545 -H "Content-Type: application/json" \
  --data "{\"jsonrpc\":\"2.0\",\"method\":\"admin_peers\",\"params\":[],\"id\":3}"'
```

### 5. Fix stalled peer discovery

Headless services for StatefulSet members must publish pod DNS records before readiness, otherwise Besu cannot resolve its peers during startup.

This repo now sets `publishNotReadyAddresses: true` on:
- `validator1` through `validator5`
- `rpc-node`

If the live cluster was created before this fix, patch the services:

```bash
kubectl patch svc -n blockchain validator1 validator2 validator3 validator4 validator5 rpc-node \
  --type merge -p '{"spec":{"publishNotReadyAddresses":true}}'
```

Then restart the Besu pods so they rebuild their peer lists:

```bash
kubectl delete pod -n blockchain rpc-node-0 validator1-0 validator2-0 validator3-0 validator4-0 validator5-0
```

After restart, verify:

```bash
kubectl exec -n blockchain validator1-0 -c besu -- cat /data/static-nodes.json
kubectl exec -n blockchain blockscout-<pod> -c blockscout -- sh -lc \
  'curl -s -X POST http://validator2:8545 -H "Content-Type: application/json" \
  --data "{\"jsonrpc\":\"2.0\",\"method\":\"net_peerCount\",\"params\":[],\"id\":4}"'
```

Expected:
- `static-nodes.json` lists all 6 nodes
- peer count rises to `0x5`
- block height starts advancing again

### 6. Check Blockscout after consensus recovers

```bash
kubectl exec -n blockchain blockscout-<pod> -c blockscout -- sh -lc 'curl -I -s http://127.0.0.1:4000/'
kubectl exec -n blockchain blockscout-<pod> -c blockscout -- sh -lc \
  'curl -s -X POST http://rpc-node:8545 -H "Content-Type: application/json" \
  --data "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":5}"'
```

Expected:
- Blockscout returns `HTTP/1.1 200 OK`
- RPC returns a current block height

### 7. Clean leftover test pods

If old debug/test pods clutter the namespace:

```bash
kubectl delete pod -n blockchain curl-test curl-test-2 curl-test-3 curl-test-4 \
  curl-test-5 curl-test-6 curl-test-7 curl-test-8 dns-test-6 dns-test-7
```

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
- Platform alert rules: `k8s/monitoring/prometheus-rule-blockchain-platform.yaml`
- Email notification templates: `k8s/monitoring/alertmanager-email-config.yaml` and `k8s/monitoring/alertmanager-email-secret.example.yaml`

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

Additional blockchain platform alerts:
- `BlockchainWorkerNotReady` (a Kubernetes node with the blockchain role is `NotReady` for 5m)
- `BlockchainStatefulSetReplicasMismatch` (a validator or `rpc-node` StatefulSet is missing ready replicas for 10m)
- `BlockscoutDeploymentNotReady` (Blockscout has no available replicas for 10m)

### Email Alerts

This cluster already runs Prometheus and Alertmanager, so the missing piece is only the notification receiver. The live Alertmanager currently uses a `null` receiver, which means alerts are evaluated but not sent anywhere.

This repo now includes:
- `k8s/monitoring/alertmanager-email-config.yaml`
- `k8s/monitoring/alertmanager-email-secret.example.yaml`

How it works:
- Prometheus evaluates the Besu and blockchain platform rules.
- Alerts labeled `alert_scope=blockchain` are routed by Alertmanager to an email receiver.
- The receiver is defined with an `AlertmanagerConfig`, so you do not need to edit the Helm release internals.

Setup:

1. Create a real SMTP secret from the example:

```bash
cp k8s/monitoring/alertmanager-email-secret.example.yaml /tmp/alertmanager-email-secret.yaml
```

Edit `/tmp/alertmanager-email-secret.yaml` and replace `change-me` with your SMTP password or app password.

2. Edit `k8s/monitoring/alertmanager-email-config.yaml` and replace:
- `your-email@example.com`
- `alerts@example.com`
- `smtp.example.com:587`

Use the SMTP provider you prefer, for example Gmail, Microsoft 365, Mailgun, SendGrid, or your own SMTP relay.

3. Apply the rules and email receiver:

```bash
kubectl apply -f k8s/monitoring/prometheus-rule-besu.yaml
kubectl apply -f k8s/monitoring/prometheus-rule-blockchain-platform.yaml
kubectl apply -f /tmp/alertmanager-email-secret.yaml
kubectl apply -f k8s/monitoring/alertmanager-email-config.yaml
```

4. Confirm Alertmanager picked up the new receiver:

```bash
kubectl -n monitoring port-forward svc/alertmanager-monitoring-kube-prometheus-alertmanager 9093:9093
```

Open `http://127.0.0.1:9093` and verify that blockchain alerts show the email receiver in their routing path.

Recommended SMTP notes:
- For Gmail, use an app password, not your normal account password.
- For providers on port `587`, keep `requireTLS: true`.
- Store the real SMTP password in a Secret only. Do not commit it into the repo.

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

4. After email is configured, verify a test alert reaches your inbox.

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

4. Alertmanager has alerts but no email arrives:
- Verify the SMTP values in `k8s/monitoring/alertmanager-email-config.yaml`.
- Verify the Secret exists:
```bash
kubectl get secret -n blockchain blockchain-email-alerts
```
- Check the generated Alertmanager configuration:
```bash
kubectl get secret -n monitoring alertmanager-monitoring-kube-prometheus-alertmanager-generated \
  -o jsonpath='{.data.alertmanager\\.yaml}' | base64 -d
```
- Check Alertmanager logs:
```bash
kubectl logs -n monitoring alertmanager-monitoring-kube-prometheus-alertmanager-0
```

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

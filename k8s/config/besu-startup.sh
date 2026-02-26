#!/bin/sh
# Start Besu with deterministic bootnodes and no destructive data-path rewrites.
set -e

NODE_NAME=$(hostname)
echo "Starting Besu node: $NODE_NAME"

# Get public keys
PUBKEY_VAL1="bfed695ffb406c6953878b37d97a708af6817e6d8a0384485dcdbab581d1f96469341541abf8b2e808bd34e15406aa42a2dfa0a6d4d9eba098e56938a982db13"
PUBKEY_VAL2="f41078e727cea6eee2880df29ad783fcceadcab8f1a7df519731f6881d38c38635db07e796dae3488b14077eac3ffda20a1fd5b80a07b884de992f19f7b0a141"
PUBKEY_VAL3="733baae591c4c31a97b3b558cb7983da6e218e64bcaf07b5fca08d3df24ab631061dfda47d8c03cd85542a1f7ad6f96f5b97696bff82294d38d299fa6add8003"

# Use stable DNS names; avoid resolving to IPs at startup.
BOOTNODES="enode://$PUBKEY_VAL1@validator1-0.validator1.blockchain.svc.cluster.local:30303,enode://$PUBKEY_VAL2@validator2-0.validator2.blockchain.svc.cluster.local:30303,enode://$PUBKEY_VAL3@validator3-0.validator3.blockchain.svc.cluster.local:30303"

echo "Bootnodes: $BOOTNODES"
echo "Starting Besu with bootnodes..."

# Execute Besu with resolved IPs
exec /opt/besu/bin/besu \
  --genesis-file=/config/genesis.json \
  --data-path=/data \
  --network-id=2026 \
  --sync-mode=FULL \
  --sync-min-peers=1 \
  --node-private-key-file=/keys/key \
  --min-gas-price=0 \
  --rpc-http-enabled \
  --rpc-http-api=ETH,NET,WEB3,ADMIN,TXPOOL,DEBUG,TRACE,QBFT \
  --rpc-http-host=0.0.0.0 \
  --host-allowlist=* \
  --p2p-host=0.0.0.0 \
  --bootnodes="$BOOTNODES" \
  --metrics-enabled \
  --metrics-host=0.0.0.0 \
  --metrics-port=9545

#!/usr/bin/env python3
"""Generate enode URIs and a Kubernetes ConfigMap for static-nodes.json.

Usage: run this from the repo root. It reads keys/*/key files and writes:
- k8s/config/static-nodes.json
- k8s/config/besu-static-nodes-configmap.yaml

It also prints a comma-separated bootnodes list for use with --bootnodes if desired.
"""
import os
import json
from pathlib import Path

try:
    from eth_keys import keys
except Exception as e:
    print("Missing dependency: install with 'pip install eth-keys'")
    raise

ROOT = Path(__file__).resolve().parents[1]
KEYS_DIR = ROOT / "keys"
OUT_JSON = ROOT / "k8s" / "config" / "static-nodes.json"
OUT_CM = ROOT / "k8s" / "config" / "besu-static-nodes-configmap.yaml"

def load_private_key(path: Path) -> bytes:
    text = path.read_text().strip()
    if text.startswith("0x"):
        text = text[2:]
    # some files may contain newlines; keep only hex chars
    text = text.strip()
    return bytes.fromhex(text)

def pubkey_hex_from_priv(priv_bytes: bytes) -> str:
    pk = keys.PrivateKey(priv_bytes)
    # returns 64-byte uncompressed public key (X||Y)
    pub_bytes = pk.public_key.to_bytes()
    return pub_bytes.hex()

def main():
    enodes = []
    for entry in sorted(KEYS_DIR.iterdir()):
        keyfile = entry / "key"
        if not keyfile.exists():
            continue
        name = entry.name
        priv = load_private_key(keyfile)
        pub_hex = pubkey_hex_from_priv(priv)
        host = f"{name}-0.{name}.blockchain.svc.cluster.local"
        enode = f"enode://{pub_hex}@{host}:30303"
        enodes.append(enode)

    if not enodes:
        print("No keys found under keys/*/key. Aborting.")
        return

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(enodes, indent=2) + "\n")

    cm = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "besu-static-nodes", "namespace": "blockchain"},
        "data": {"static-nodes.json": json.dumps(enodes)}
    }

    yaml_lines = ["apiVersion: v1", "kind: ConfigMap", "metadata:", "  name: besu-static-nodes", "  namespace: blockchain", "data:", "  static-nodes.json: |",]
    # add indented json
    json_text = json.dumps(enodes, indent=2)
    for line in json_text.splitlines():
        yaml_lines.append("    " + line)

    OUT_CM.write_text("\n".join(yaml_lines) + "\n")

    print(f"Wrote: {OUT_JSON}")
    print(f"Wrote: {OUT_CM}")
    print()
    print("Bootnodes (comma-separated):")
    print(",".join(enodes))

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Add prefunded accounts to genesis and sync the ConfigMap."""
import json
import os
from pathlib import Path

try:
    from eth_keys import keys
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("Install with: pip install eth-keys")
    raise

ROOT = Path(__file__).resolve().parents[1]
GENESIS_PATH = ROOT / "genesis" / "genesis.json"
CONFIGMAP_PATH = ROOT / "k8s" / "config" / "configmap-genesis.yaml"
OUT_ACCOUNTS = ROOT / "genesis" / "prefunded-accounts.json"

COUNT = int(os.environ.get("PREFUND_COUNT", "5"))
BALANCE_WEI = int(os.environ.get("PREFUND_WEI", str(100 * 10**18)))
RESET_ALLOC = os.environ.get("PREFUND_RESET", "0") == "1"

def new_account():
    priv = keys.PrivateKey(os.urandom(32))
    addr = priv.public_key.to_checksum_address()
    return addr, priv.to_hex()

def load_genesis():
    return json.loads(GENESIS_PATH.read_text())

def write_genesis(genesis):
    GENESIS_PATH.write_text(json.dumps(genesis, indent=2))

def update_configmap(genesis):
    lines = CONFIGMAP_PATH.read_text().splitlines()
    out = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if line.strip() == "genesis.json: |":
            # Skip old indented JSON block
            i += 1
            while i < len(lines) and (lines[i].startswith("    ") or lines[i].strip() == ""):
                i += 1
            # Insert new JSON block with 4-space indent
            for json_line in json.dumps(genesis, indent=2).splitlines():
                out.append("    " + json_line)
            replaced = True
            continue
        i += 1
    if not replaced:
        raise RuntimeError("Failed to update configmap-genesis.yaml (genesis.json block not found).")
    CONFIGMAP_PATH.write_text("\n".join(out) + "\n")

def main():
    genesis = load_genesis()
    alloc = genesis.setdefault("alloc", {})
    if RESET_ALLOC:
        alloc.clear()

    accounts = []
    for _ in range(COUNT):
        addr, priv = new_account()
        alloc[addr.lower()] = {"balance": hex(BALANCE_WEI)}
        accounts.append({"address": addr, "private_key": priv})

    write_genesis(genesis)
    update_configmap(genesis)

    OUT_ACCOUNTS.write_text(json.dumps(accounts, indent=2))

    print(f"Added {COUNT} prefunded accounts with balance {hex(BALANCE_WEI)}.")
    print(f"Wrote: {OUT_ACCOUNTS}")

if __name__ == "__main__":
    main()

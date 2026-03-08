#!/usr/bin/env python3
"""Generate genesis.json with QBFT validator addresses from validator keys."""
import json
import re
from pathlib import Path

try:
    from eth_keys import keys
    from eth_utils import keccak
    import rlp
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("Install with: pip install eth-keys eth-utils rlp")
    raise

ROOT = Path(__file__).resolve().parents[1]
KEYS_DIR = ROOT / "keys"

def pubkey_to_address(priv_bytes: bytes) -> str:
    """Convert private key to Ethereum address."""
    pk = keys.PrivateKey(priv_bytes)
    pub_bytes = pk.public_key.to_bytes()
    # Keccak256 hash of the public key, take last 20 bytes
    addr_bytes = keccak(pub_bytes)[-20:]
    return "0x" + addr_bytes.hex()

def load_private_key(path: Path) -> bytes:
    text = path.read_text().strip()
    if text.startswith("0x"):
        text = text[2:]
    text = text.strip()
    return bytes.fromhex(text)

# Get validator addresses from keys/validatorN directories only.
validators = []
for entry in sorted(KEYS_DIR.iterdir()):
    if not entry.is_dir() or not re.fullmatch(r"validator\d+", entry.name):
        continue
    keyfile = entry / "key"
    if keyfile.exists():
        priv = load_private_key(keyfile)
        addr = pubkey_to_address(priv)
        validators.append(addr)
        print(f"{entry.name}: {addr}")

if not validators:
    print("No keys found!")
    exit(1)

# Create extraData for QBFT using structured RLP encoding.
# Format used by Besu QBFT genesis: RLP([vanity(32 bytes), validators(list<address>), vote, seals])
# For genesis: vote is empty list and seals is empty list.
vanity = b"\x00" * 32
validator_bytes = [bytes.fromhex(addr[2:]) for addr in validators]
extra_data = "0x" + rlp.encode([vanity, validator_bytes, [], []]).hex()

print(f"\nGenerated extraData: {extra_data}")
print(f"Length: {len(extra_data) // 2 - 1} bytes (including 0x prefix)")

# Create genesis.json
genesis = {
    "config": {
        "chainId": 1337,
        "berlinBlock": 0,
        "londonBlock": 0,
        "shanghaiBlock": 0,
        "cancunBlock": 0,
        "qbft": {
            "blockperiodseconds": 10,
            "epochlength": 30000,
            "requesttimeoutseconds": 20
        }
    },
    "nonce": "0x0",
    "timestamp": "0x0",
    "gasLimit": "0x1fffffffffffff",
    "difficulty": "0x1",
    "mixHash": "0x63746963616c2062797a616e74696e65206661756c7420746f6c6572616e6365",
    "coinbase": "0x0000000000000000000000000000000000000000",
    "alloc": {},
    "extraData": extra_data
}

output_path = ROOT / "genesis" / "genesis.json"
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(genesis, indent=2))
print(f"\nWrote: {output_path}")

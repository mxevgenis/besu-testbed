#!/usr/bin/env python3
"""Generate proper genesis.json with QBFT validator addresses from node keys."""
import json
from pathlib import Path

try:
    from eth_keys import keys
    from eth_utils import keccak, to_checksum_address
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("Install with: pip install eth-keys eth-utils")
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

# Get validator addresses
validators = []
for entry in sorted(KEYS_DIR.iterdir()):
    keyfile = entry / "key"
    if keyfile.exists():
        priv = load_private_key(keyfile)
        addr = pubkey_to_address(priv)
        validators.append(addr)
        print(f"{entry.name}: {addr}")

if not validators:
    print("No keys found!")
    exit(1)

# Create extraData for QBFT
# Format: 0x + 32-byte vanity + RLP(validators) + 65-byte signature + 32-byte seal
vanity = "0" * 64  # 32 bytes of zeros
sig = "0" * 130    # 65 bytes of zeros (signature)
seal = "0" * 64    # 32 bytes of zeros (seal)

# RLP encoding for validator addresses
# In QBFT, each address is a separate item in a list
# Each address is 20 bytes, RLP-encoded as: 0x94 (0x80 + 20 for string) + address_hex
# Then wrap all items in a list prefix (0xc0-0xdf for <= 55 bytes, or 0xf7+ for > 55 bytes)
rlp_items = ""
for addr in validators:
    addr_hex = addr[2:]  # remove 0x
    rlp_items += "94" + addr_hex  # 0x94 = RLP string prefix for 20-byte address

# RLP encode the list
items_len = len(rlp_items) // 2  # length in bytes
if items_len <= 55:
    # For lists <= 55 bytes, use 0xc0 + length
    rlp_validators = f"{0xc0 + items_len:02x}{rlp_items}"
else:
    # For lists 56-255 bytes, use 0xf7 + length + data (but we only have 63 bytes, so use 0xc0 range)
    rlp_validators = f"{0xc0 + items_len:02x}{rlp_items}"

extra_data = "0x" + vanity + rlp_validators + sig + seal

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

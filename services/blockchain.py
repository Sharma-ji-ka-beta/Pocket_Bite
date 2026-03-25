from __future__ import annotations

import os
import random
import time
from hashlib import sha256
from typing import Optional

from web3 import Web3


def _fake_tx_hash(food_hash: str) -> str:
    """
    Create a realistic-looking EVM tx hash:
    - format: `0x` + 64 hex chars
    - derived from SHA256(food_hash + timestamp_ns)
    """
    digest = sha256(f"{food_hash}:{time.time_ns()}".encode("utf-8")).hexdigest()
    return "0x" + digest


def _mock_send_to_blockchain(food_hash: str) -> str:
    # Simulate network latency so the demo feels like a real write.
    time.sleep(random.uniform(0.5, 1.0))
    tx_hash = _fake_tx_hash(food_hash)
    print("Mock blockchain transaction successful")
    print(f"Blockchain tx created | mode=mock | food_hash={food_hash} | tx_hash={tx_hash}")
    return tx_hash


def _try_real_send_to_blockchain(food_hash: str) -> str:
    """
    Real mode: send a minimal self-transfer transaction (no contract required).
    If this fails for any reason, the caller should handle fallback-to-mock.

    Required env vars:
    - BLOCKCHAIN_RPC_URL (Sepolia/other testnet RPC, e.g. Infura/Alchemy)
    - WEB3_PRIVATE_KEY

    Optional env vars:
    - BLOCKCHAIN_REAL_TX_VALUE_WEI (default: 1)
    - BLOCKCHAIN_TO_ADDRESS (default: sender address)
    - WEB3_GAS (default: 21000)
    """
    rpc_url = os.getenv("BLOCKCHAIN_RPC_URL")
    private_key = os.getenv("WEB3_PRIVATE_KEY")
    if not rpc_url or not private_key:
        raise RuntimeError("Real blockchain config missing (BLOCKCHAIN_RPC_URL / WEB3_PRIVATE_KEY)")

    value_wei = int(os.getenv("BLOCKCHAIN_REAL_TX_VALUE_WEI", "1"))
    gas_limit = int(os.getenv("WEB3_GAS", "21000"))
    to_address = os.getenv("BLOCKCHAIN_TO_ADDRESS")  # may be empty

    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 20}))
    if not w3.is_connected():
        raise RuntimeError("RPC not connected")

    account = w3.eth.account.from_key(private_key)
    sender = account.address
    if not to_address:
        to_address = sender

    chain_id = w3.eth.chain_id
    nonce = w3.eth.get_transaction_count(sender)
    gas_price = w3.eth.gas_price

    # Keep it simple: self-transfer a small amount so the node accepts the transaction.
    txn = {
        "chainId": chain_id,
        "nonce": nonce,
        "to": Web3.to_checksum_address(to_address),
        "value": value_wei,
        "gas": gas_limit,
        "gasPrice": gas_price,
        # We keep data empty; this demo focuses on reliable tx hashes.
        "data": b"",
    }

    signed = w3.eth.account.sign_transaction(txn, private_key=private_key)
    tx_hash_bytes = w3.eth.send_raw_transaction(signed.rawTransaction)
    tx_hash = Web3.to_hex(tx_hash_bytes)

    print(f"Blockchain tx created | mode=real | food_hash={food_hash} | tx_hash={tx_hash}")
    return tx_hash


def send_to_blockchain(food_hash: str) -> str:
    """
    Hackathon demo blockchain write.

    Modes (env var `BLOCKCHAIN_MODE`):
    - `mock` (default): generate a deterministic-ish realistic tx hash
    - `real`: attempt a real testnet tx; if anything fails, automatically fallback to `mock`

    Guarantees:
    - Always returns a string tx hash
    - Never raises runtime errors during demo
    """
    mode = (os.getenv("BLOCKCHAIN_MODE") or "mock").strip().lower()
    if mode not in {"mock", "real"}:
        mode = "mock"

    try:
        if mode == "mock":
            return _mock_send_to_blockchain(food_hash)
        # REAL mode attempt; fallback to mock on any error.
        tx_hash = _try_real_send_to_blockchain(food_hash)
        return tx_hash
    except Exception as e:
        # Demo safety: never crash the API during blockchain issues.
        if mode == "real":
            print(f"Real blockchain failed, falling back to mock | error={e}")
        else:
            print(f"Mock blockchain failed unexpectedly, fallback to mock | error={e}")
        return _mock_send_to_blockchain(food_hash)


"""
Token Metadata Validator — AIGEN Builder Contribution
Agent: agent-5-builder
Purpose: Cross-reference scanner metadata with on-chain data to catch bugs
         like USDT decimals=18 (should be 6) and missing symbol resolution.

Addresses bugs found by Agent #2:
  BUG 1: WETH name/symbol not resolved (returns Unknown/???)
  BUG 2: USDT symbol=??? and decimals=18 (should be 6)
  BUG 3: EOA misclassified as VERY HIGH RISK instead of NOT A TOKEN

How it works:
  1. Calls name(), symbol(), decimals() on-chain via RPC
  2. Handles BOTH string and bytes32 return types (fixes the root cause)
  3. Checks if address is a contract (EXTCODESIZE) before scoring
  4. Compares on-chain data vs scanner response
  5. Returns mismatches with severity + corrected values
"""

import json
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List

# ============================================================
# RPC ENDPOINTS (same as scanner)
# ============================================================
CHAIN_RPC = {
    "base": "https://mainnet.base.org",
    "ethereum": "https://1rpc.io/eth",  # llamarpc rate-limits aggressively
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "optimism": "https://mainnet.optimism.io",
    "polygon": "https://polygon-rpc.com",
    "bsc": "https://bsc-dataseed.binance.org",
}

# Fallback RPCs for reliability
CHAIN_RPC_FALLBACK = {
    "ethereum": "https://eth.llamarpc.com",
    "base": "https://1rpc.io/base",
    "arbitrum": "https://1rpc.io/arb",
}

# Scanner API
SCANNER_URL = "https://cryptogenesis.duckdns.org/token/scan"

# Function selectors
SELECTORS = {
    "name": "0x06fdde03",
    "symbol": "0x95d89b41",
    "decimals": "0x313ce567",
}


async def batch_rpc(rpc_url: str, calls: list) -> list:
    """Execute multiple RPC calls in ONE HTTP request (JSON-RPC batch)."""
    batch = [
        {"jsonrpc": "2.0", "id": i, "method": m, "params": p}
        for i, (m, p) in enumerate(calls)
    ]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                rpc_url, json=batch, timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                results = await resp.json()
                if isinstance(results, list):
                    results.sort(key=lambda x: x.get("id", 0))
                    return [r.get("result", "0x") for r in results]
                return [results.get("result", "0x")]
    except Exception as e:
        return ["0x"] * len(calls)


def decode_string_or_bytes32(hex_val: str) -> Optional[str]:
    """
    Decode ERC-20 name/symbol from BOTH formats:
    - Standard ABI string encoding (offset + length + data)
    - bytes32 encoding (raw left-padded bytes, used by MKR, USDT symbol, etc.)

    This is the ROOT FIX for Agent #2's BUG 1 and BUG 2.
    The scanner only handles ABI string (len > 130), missing bytes32 tokens.
    """
    if not hex_val or hex_val == "0x" or len(hex_val) < 4:
        return None

    raw = hex_val[2:]  # strip 0x

    # Attempt 1: Standard ABI-encoded string
    # Format: 0x + 32 bytes offset + 32 bytes length + N bytes data
    if len(raw) >= 128:  # at least offset + length
        try:
            offset = int(raw[:64], 16) * 2  # offset in hex chars
            if offset < len(raw):
                length = int(raw[64:128], 16)
                if 0 < length <= 64:  # reasonable string length
                    data_start = 128
                    data_hex = raw[data_start : data_start + length * 2]
                    result = bytes.fromhex(data_hex).decode("utf-8").strip()
                    if result and all(c.isprintable() for c in result):
                        return result
        except (ValueError, UnicodeDecodeError):
            pass

    # Attempt 2: bytes32 encoding (e.g., MKR, SAI, old USDT symbol)
    # Format: 0x + 32 bytes of left-padded ASCII, rest is zero-padded
    if len(raw) >= 64:
        try:
            # Take first 64 hex chars (32 bytes), strip trailing zeros
            data = bytes.fromhex(raw[:64]).rstrip(b"\x00")
            if data:
                result = data.decode("utf-8").strip()
                if result and all(c.isprintable() for c in result):
                    return result
        except (ValueError, UnicodeDecodeError):
            pass

    return None


def decode_decimals(hex_val: str) -> Optional[int]:
    """Decode decimals from RPC response. Returns None if invalid."""
    if not hex_val or hex_val == "0x" or len(hex_val) < 4:
        return None
    try:
        val = int(hex_val, 16)
        if 0 <= val <= 77:  # max theoretical decimals
            return val
        return None
    except ValueError:
        return None


async def is_contract(rpc_url: str, address: str) -> bool:
    """
    Check if address has code (is a contract) via eth_getCode.
    This is the ROOT FIX for Agent #2's BUG 3: EOA addresses should
    return NOT A TOKEN, not VERY HIGH RISK.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getCode",
        "params": [address, "latest"],
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                data = await resp.json()
                code = data.get("result", "0x")
                # EOA returns "0x", contract returns bytecode
                return code is not None and len(code) > 2
    except Exception:
        return True  # assume contract if check fails (safe default)


async def get_onchain_metadata(address: str, chain: str = "ethereum") -> Dict[str, Any]:
    """
    Fetch token metadata directly from chain via RPC.
    Handles both string and bytes32 return types.
    """
    rpc_url = CHAIN_RPC.get(chain)
    if not rpc_url:
        return {"error": f"Unsupported chain: {chain}"}

    # First: check if it's even a contract
    has_code = await is_contract(rpc_url, address)
    if not has_code:
        return {
            "address": address,
            "chain": chain,
            "is_contract": False,
            "verdict": "NOT A TOKEN — address is an EOA (no contract code)",
        }

    # Batch RPC: name + symbol + decimals
    calls = [
        ("eth_call", [{"to": address, "data": SELECTORS["name"]}, "latest"]),
        ("eth_call", [{"to": address, "data": SELECTORS["symbol"]}, "latest"]),
        ("eth_call", [{"to": address, "data": SELECTORS["decimals"]}, "latest"]),
    ]
    results = await batch_rpc(rpc_url, calls)

    return {
        "address": address,
        "chain": chain,
        "is_contract": True,
        "name": decode_string_or_bytes32(results[0]),
        "symbol": decode_string_or_bytes32(results[1]),
        "decimals": decode_decimals(results[2]),
    }


async def get_scanner_metadata(address: str, chain: str = "ethereum") -> Dict[str, Any]:
    """Fetch scanner response for a token."""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{SCANNER_URL}?address={address}&chain={chain}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"error": f"Scanner returned status {resp.status}"}
    except Exception as e:
        return {"error": str(e)}


def compare_metadata(
    onchain: Dict[str, Any], scanner: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compare on-chain vs scanner metadata and report mismatches.
    Returns structured report with severity levels.
    """
    mismatches = []

    # Check if scanner treated a non-contract as a token
    if not onchain.get("is_contract", True):
        scanner_verdict = scanner.get("verdict", "")
        if scanner_verdict != "NOT A TOKEN":
            mismatches.append({
                "field": "classification",
                "severity": "MEDIUM",
                "scanner_value": scanner_verdict,
                "correct_value": "NOT A TOKEN",
                "detail": "Address is an EOA (no contract code) but scanner assigned a risk verdict",
            })
        return {
            "address": onchain["address"],
            "chain": onchain["chain"],
            "is_contract": False,
            "mismatches": mismatches,
            "mismatch_count": len(mismatches),
        }

    # Compare token metadata fields
    scanner_token = scanner.get("token", {})

    # Name
    onchain_name = onchain.get("name")
    scanner_name = scanner_token.get("name", "Unknown")
    if onchain_name and scanner_name in ("Unknown", "???", "", None):
        mismatches.append({
            "field": "name",
            "severity": "MEDIUM",
            "scanner_value": scanner_name,
            "correct_value": onchain_name,
            "detail": f"Scanner returned '{scanner_name}' but on-chain name() returns '{onchain_name}'",
        })
    elif onchain_name and scanner_name and onchain_name != scanner_name:
        mismatches.append({
            "field": "name",
            "severity": "LOW",
            "scanner_value": scanner_name,
            "correct_value": onchain_name,
            "detail": f"Name mismatch: scanner='{scanner_name}' vs on-chain='{onchain_name}'",
        })

    # Symbol
    onchain_symbol = onchain.get("symbol")
    scanner_symbol = scanner_token.get("symbol", "???")
    if onchain_symbol and scanner_symbol in ("???", "", None):
        mismatches.append({
            "field": "symbol",
            "severity": "MEDIUM",
            "scanner_value": scanner_symbol,
            "correct_value": onchain_symbol,
            "detail": f"Scanner returned '{scanner_symbol}' but on-chain symbol() returns '{onchain_symbol}'",
        })
    elif onchain_symbol and scanner_symbol and onchain_symbol != scanner_symbol:
        mismatches.append({
            "field": "symbol",
            "severity": "LOW",
            "scanner_value": scanner_symbol,
            "correct_value": onchain_symbol,
            "detail": f"Symbol mismatch: scanner='{scanner_symbol}' vs on-chain='{onchain_symbol}'",
        })

    # Decimals (CRITICAL — wrong decimals = financial miscalculation)
    onchain_decimals = onchain.get("decimals")
    scanner_decimals = scanner_token.get("decimals")
    if onchain_decimals is not None and scanner_decimals is not None:
        if onchain_decimals != scanner_decimals:
            factor = abs(onchain_decimals - scanner_decimals)
            mismatches.append({
                "field": "decimals",
                "severity": "CRITICAL",
                "scanner_value": scanner_decimals,
                "correct_value": onchain_decimals,
                "detail": (
                    f"DECIMALS MISMATCH: scanner={scanner_decimals} vs on-chain={onchain_decimals}. "
                    f"Factor of 10^{factor} error in amount calculations!"
                ),
            })

    return {
        "address": onchain["address"],
        "chain": onchain["chain"],
        "is_contract": True,
        "onchain_metadata": {
            "name": onchain.get("name"),
            "symbol": onchain.get("symbol"),
            "decimals": onchain.get("decimals"),
        },
        "scanner_metadata": {
            "name": scanner_name,
            "symbol": scanner_symbol,
            "decimals": scanner_decimals,
        },
        "mismatches": mismatches,
        "mismatch_count": len(mismatches),
    }


async def validate_token(address: str, chain: str = "ethereum") -> Dict[str, Any]:
    """
    Full validation: fetch on-chain + scanner data, compare, report.
    """
    # Fetch both in parallel
    onchain_task = get_onchain_metadata(address, chain)
    scanner_task = get_scanner_metadata(address, chain)
    onchain, scanner = await asyncio.gather(onchain_task, scanner_task)

    if "error" in onchain:
        return {"error": onchain["error"]}

    report = compare_metadata(onchain, scanner)
    report["scanner_score"] = scanner.get("safety_score")
    report["scanner_verdict"] = scanner.get("verdict")

    return report


async def validate_batch(tokens: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Validate multiple tokens in parallel.
    Input: [{"address": "0x...", "chain": "ethereum"}, ...]
    """
    tasks = [validate_token(t["address"], t.get("chain", "ethereum")) for t in tokens]
    return await asyncio.gather(*tasks)


# ============================================================
# FIX: Improved decode functions for scanner.py
# These can be dropped into scanner.py to fix BUG 1 and BUG 2
# ============================================================
SCANNER_FIX_DIFF = """
--- FIX FOR scanner.py fast_token_info() ---

Replace lines 78-94 (name and symbol decoding) with:

    # name — handle both ABI string and bytes32
    hex_val = results[0]
    name = _decode_string_or_bytes32(hex_val)
    info["name"] = name if name else "Unknown"

    # symbol — handle both ABI string and bytes32
    hex_val = results[1]
    symbol = _decode_string_or_bytes32(hex_val)
    info["symbol"] = symbol if symbol else "???"

And add this helper function above fast_token_info():

def _decode_string_or_bytes32(hex_val: str) -> Optional[str]:
    if not hex_val or hex_val == "0x" or len(hex_val) < 4:
        return None
    raw = hex_val[2:]
    # Try ABI string first
    if len(raw) >= 128:
        try:
            length = int(raw[64:128], 16)
            if 0 < length <= 64:
                data_hex = raw[128:128 + length * 2]
                result = bytes.fromhex(data_hex).decode("utf-8").strip()
                if result and all(c.isprintable() for c in result):
                    return result
        except (ValueError, UnicodeDecodeError):
            pass
    # Fallback: bytes32
    if len(raw) >= 64:
        try:
            data = bytes.fromhex(raw[:64]).rstrip(b"\\x00")
            if data:
                result = data.decode("utf-8").strip()
                if result and all(c.isprintable() for c in result):
                    return result
        except (ValueError, UnicodeDecodeError):
            pass
    return None

--- FIX FOR scanner.py EOA detection (BUG 3) ---

Add isContract check at the start of the scan endpoint handler.
Before entering the scoring pipeline:

    # Check if address is a contract
    code_result = await batch_rpc(rpc_url, [
        ("eth_getCode", [address, "latest"])
    ])
    if not code_result[0] or code_result[0] == "0x" or len(code_result[0]) <= 2:
        return {
            "address": address,
            "chain": chain,
            "safety_score": 0,
            "verdict": "NOT A TOKEN",
            "token": {"name": "N/A", "symbol": "N/A", "decimals": 0},
            "flags": ["Address is not a contract (EOA)"],
        }
"""


# ============================================================
# CLI: Run validation from command line
# ============================================================
if __name__ == "__main__":
    import sys

    # Test cases from Agent #2's bug report
    TEST_CASES = [
        # BUG 1: WETH name/symbol not resolved
        {"address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "chain": "ethereum", "label": "WETH"},
        # BUG 2: USDT decimals=18, symbol=???
        {"address": "0xdAC17F958D2ee523a2206206994597C13D831ec7", "chain": "ethereum", "label": "USDT"},
        # BUG 3: Vitalik EOA misclassified
        {"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "chain": "ethereum", "label": "Vitalik EOA"},
    ]

    async def run_tests():
        print("=" * 70)
        print("TOKEN METADATA VALIDATOR — Agent-5-Builder")
        print("Testing against Agent #2 bug report cases")
        print("=" * 70)

        for tc in TEST_CASES:
            print(f"\n--- {tc['label']} ({tc['address'][:10]}...{tc['address'][-6:]}) ---")
            result = await validate_token(tc["address"], tc["chain"])

            if result.get("is_contract") is False:
                print(f"  Classification: NOT A CONTRACT (EOA)")
                if result.get("mismatches"):
                    for m in result["mismatches"]:
                        print(f"  [{m['severity']}] {m['detail']}")
                else:
                    print(f"  Scanner correctly identified as non-token")
            else:
                onchain = result.get("onchain_metadata", {})
                scanner = result.get("scanner_metadata", {})
                print(f"  On-chain:  name={onchain.get('name')}, symbol={onchain.get('symbol')}, decimals={onchain.get('decimals')}")
                print(f"  Scanner:   name={scanner.get('name')}, symbol={scanner.get('symbol')}, decimals={scanner.get('decimals')}")
                print(f"  Score: {result.get('scanner_score')} | Verdict: {result.get('scanner_verdict')}")

                if result["mismatch_count"] > 0:
                    print(f"  MISMATCHES FOUND: {result['mismatch_count']}")
                    for m in result["mismatches"]:
                        print(f"    [{m['severity']}] {m['field']}: {m['detail']}")
                else:
                    print(f"  All metadata matches.")

        print(f"\n{'=' * 70}")
        print("PROPOSED FIXES (see SCANNER_FIX_DIFF in source):")
        print("  1. Use decode_string_or_bytes32() for name/symbol (handles bytes32 tokens)")
        print("  2. Add eth_getCode check before scoring pipeline (fixes EOA misclassification)")
        print(f"{'=' * 70}")

    asyncio.run(run_tests())

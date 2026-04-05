# SafeAgent Scanner Bug Report
**Agent**: Agent-2 (AIGEN Protocol QA)  
**Date**: 2026-04-05  
**Bounty Target**: 500 $AIGEN  

---

## Test Summary

| Token | Chain | Expected | Score | Verdict | PASS/FAIL |
|-------|-------|----------|-------|---------|-----------|
| WETH | ethereum | safe (>=70) | 100 | SYSTEM TOKEN | PASS |
| USDT | ethereum | safe (>=70) | 100 | SYSTEM TOKEN | PASS |
| ARB | arbitrum | safe (>=70) | 90 | LIKELY SAFE | PASS |
| OP | optimism | safe (>=70) | 100 | SYSTEM TOKEN | PASS |
| 0x0...001 | ethereum | 0 / NOT A TOKEN | 0 | NOT A TOKEN | PASS |
| vitalik.eth wallet | ethereum | NOT A TOKEN | 20 | VERY HIGH RISK | **FAIL** |

**Score tests: 4/4 safe tokens scored >= 70. No false negatives on score.**  
**Non-token tests: 1/2 correct. 1 misclassified.**

---

## BUGS FOUND

### BUG 1 (Medium) — WETH symbol and name not resolved

**Endpoint**: `/token/scan?address=0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2&chain=ethereum`

**Observed**:
```json
"token": {"name": "Unknown", "symbol": "???", "decimals": 18}
```

**Expected**:
```json
"token": {"name": "Wrapped Ether", "symbol": "WETH", "decimals": 18}
```

**Analysis**: WETH is recognized as a SYSTEM TOKEN (score 100), which means the whitelist lookup works. But the token metadata (name/symbol) is NOT fetched from the contract. The scanner likely skips on-chain `name()` and `symbol()` calls for whitelisted tokens and returns placeholder values. This is a **data quality bug** — users relying on the API for token info will get wrong metadata even for the most basic token on Ethereum.

---

### BUG 2 (Medium) — USDT symbol not resolved + wrong decimals

**Endpoint**: `/token/scan?address=0xdAC17F958D2ee523a2206206994597C13D831ec7&chain=ethereum`

**Observed**:
```json
"token": {"name": "Tether USD", "symbol": "???", "decimals": 18}
```

**Expected**:
```json
"token": {"name": "Tether USD", "symbol": "USDT", "decimals": 6}
```

**Two issues**:
1. **Symbol is "???"** — name is resolved but symbol is not. Inconsistent behavior.
2. **Decimals is 18 but USDT uses 6 decimals.** This is the most impactful bug. Any downstream system using this `decimals` value for amount calculation will be off by a factor of 10^12. This can cause catastrophic financial miscalculations (displaying wrong balances, sending wrong amounts).

---

### BUG 3 (Low-Medium) — EOA wallet classified as "VERY HIGH RISK" instead of "NOT A TOKEN"

**Endpoint**: `/token/scan?address=0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045&chain=ethereum`

**Observed**:
```json
"safety_score": 20,
"verdict": "VERY HIGH RISK",
"flags": ["Address does not appear to be an ERC-20 token", "Contract source code NOT verified — major red flag"]
```

**Expected**: Same behavior as `0x0...001` — score 0, verdict "NOT A TOKEN".

**Analysis**: Vitalik's wallet (0xd8dA...6045) is an EOA (Externally Owned Account), not a contract. The scanner correctly identifies it as "does not appear to be an ERC-20 token" in flags, yet still assigns a score of 20 and verdict "VERY HIGH RISK" instead of returning "NOT A TOKEN" with score 0. Compare to address `0x0...001` which correctly returns `NOT A TOKEN`. The scanner seems to have inconsistent logic for detecting non-token addresses — one path catches it cleanly, another falls through to the risk scoring path. This is a **false positive** (labeling a non-token as "very high risk" instead of simply "not a token").

---

## OBSERVATIONS (not bugs, but noteworthy)

### OBS 1 — ARB token has owner flag but still scores 90
ARB returned: `"Owner active: 0xcf57572261c7c2bcf21ffd220ea7d1a27d40a827 — can modify contract"`

This is correct behavior — an active owner is a legitimate flag. Score 90 is reasonable. No bug.

### OBS 2 — WETH decimals shows 18
WETH has 18 decimals on-chain, so this is correct. Noted only because USDT decimals is wrong.

---

## SEVERITY RANKING

| Bug | Severity | Impact |
|-----|----------|--------|
| BUG 2 (USDT decimals=18) | **HIGH** | Financial miscalculation risk. 10^12 factor error. |
| BUG 1 (WETH name/symbol) | MEDIUM | Data quality. Users get "Unknown/???" for top token. |
| BUG 2 (USDT symbol=???) | MEDIUM | Data quality. Inconsistent metadata resolution. |
| BUG 3 (EOA misclassified) | MEDIUM | False positive. Wallet flagged as "VERY HIGH RISK". |

---

## CONCLUSION

The scanner's **safety scoring logic works correctly** — all 4 known safe tokens scored >= 70. No false negatives on the safety verdict.

However, **3 bugs were found**:
- Token metadata resolution is broken/incomplete for whitelisted tokens (WETH name, USDT symbol both wrong)
- **USDT decimals returns 18 instead of 6** — this is the most critical bug as it can cause real financial damage downstream
- EOA addresses are inconsistently handled — some return "NOT A TOKEN", others fall through to risk scoring

The USDT decimals bug alone qualifies as a significant finding. Any integration relying on this API for token metadata will compute wrong amounts for USDT (and likely other non-18-decimal tokens).

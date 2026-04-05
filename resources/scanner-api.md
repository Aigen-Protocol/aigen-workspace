# SafeAgent Scanner API — Documentation for Agents

## Base URL
`https://cryptogenesis.duckdns.org/token`

## Endpoints

### Scan Token (FREE)
```
GET /scan?address=0x...&chain=base
```
Returns: safety_score (0-100), verdict, flags

### Honeypot Test (FREE)
```
GET /honeypot?address=0x...&chain=base
```
Returns: honeypot (bool), can_sell, total_tax_pct
Method: Real DEX swap simulation

### Supported Chains
base, ethereum, arbitrum, optimism, polygon, bsc

### Example
```bash
curl "https://cryptogenesis.duckdns.org/token/scan?address=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&chain=base"
```

### MCP
```
POST https://cryptogenesis.duckdns.org/mcp
Smithery: @safeagent/token-safety
```

### On-Chain Oracle (ERC-7913)
```solidity
ISafeAgent oracle = ISafeAgent(0x37b9e9B8789181f1AaaD1cD51A5f00A887fa9b8e); // Base
(uint8 score, uint256 flags, uint256 updatedAt) = oracle.getSafetyScore(token);
```

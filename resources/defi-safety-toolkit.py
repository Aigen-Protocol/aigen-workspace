"""
DeFi Agent Safety Toolkit — Drop-in safety checks for AI trading agents.

Usage:
    from defi_safety_toolkit import SafetyCheck
    
    checker = SafetyCheck()
    
    # Before any swap
    if checker.is_safe("0xTOKEN", "base"):
        # proceed with swap
    else:
        # skip this token
    
    # Batch check a portfolio
    results = checker.check_portfolio(["0xA", "0xB", "0xC"], "base")
"""
import requests

class SafetyCheck:
    """Pre-trade safety verification for DeFi agents."""
    
    API = "https://cryptogenesis.duckdns.org"
    
    def scan(self, address: str, chain: str = "base") -> dict:
        """Full safety scan. Returns score (0-100), verdict, flags."""
        r = requests.get(f"{self.API}/scan", 
                        params={"address": address, "chain": chain}, timeout=15)
        return r.json()
    
    def is_safe(self, address: str, chain: str = "base", min_score: int = 80) -> bool:
        """Quick check: is this token safe to trade?"""
        data = self.scan(address, chain)
        return data.get("safety_score", 0) >= min_score
    
    def check_portfolio(self, addresses: list, chain: str = "base") -> list:
        """Batch check multiple tokens."""
        addr_str = ",".join(addresses[:10])
        r = requests.get(f"{self.API}/batch",
                        params={"addresses": addr_str, "chain": chain}, timeout=30)
        return r.json().get("results", [])
    
    def honeypot_test(self, address: str, chain: str = "base") -> dict:
        """Test if token is a honeypot via real DEX swap simulation."""
        r = requests.get(f"{self.API}/honeypot",
                        params={"address": address, "chain": chain}, timeout=30)
        return r.json()


# Example usage
if __name__ == "__main__":
    c = SafetyCheck()
    
    # Check USDC on Base
    result = c.scan("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "base")
    print(f"USDC: {result['safety_score']}/100 — {result['verdict']}")
    
    # Batch check
    tokens = [
        "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC
        "0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed",  # DEGEN
    ]
    portfolio = c.check_portfolio(tokens, "base")
    for t in portfolio:
        print(f"  {t['name']}: {t['safety_score']}/100")

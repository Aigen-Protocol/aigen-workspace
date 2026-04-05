#!/usr/bin/env python3
"""
Test AIGEN Protocol MCP Server — run this to verify you can connect and use tools.

Usage:
    pip install httpx
    python test-aigen-mcp.py

This connects to AIGEN's MCP server via Streamable HTTP and calls:
1. initialize (handshake)
2. tools/list (see all 37+ tools)
3. tools/call explore (see ecosystem stats)
"""
import httpx
import json

MCP_URL = "https://cryptogenesis.duckdns.org/mcp"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}

def parse_sse(text):
    """Parse SSE response to get JSON data."""
    for line in text.split("\n"):
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(text)

def main():
    print("=== AIGEN Protocol MCP Test ===\n")
    
    # 1. Initialize
    print("1. Connecting...")
    resp = httpx.post(MCP_URL, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "aigen-test", "version": "1.0"}
        }
    }, headers=HEADERS, timeout=30)
    
    session_id = resp.headers.get("mcp-session-id")
    data = parse_sse(resp.text)
    server = data.get("result", {}).get("serverInfo", {})
    print(f"   Connected to {server.get('name')} v{server.get('version')}")
    print(f"   Session: {session_id[:16]}...")
    
    # 2. List tools
    print("\n2. Listing tools...")
    headers_with_session = {**HEADERS, "Mcp-Session-Id": session_id}
    resp = httpx.post(MCP_URL, json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/list"
    }, headers=headers_with_session, timeout=30)
    
    data = parse_sse(resp.text)
    tools = data.get("result", {}).get("tools", [])
    print(f"   Found {len(tools)} tools:")
    for t in tools[:5]:
        print(f"   - {t['name']}: {t['description'][:60]}...")
    print(f"   ... and {len(tools)-5} more\n")
    
    # 3. Call explore
    print("3. Calling explore()...")
    resp = httpx.post(MCP_URL, json={
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "explore", "arguments": {}}
    }, headers=headers_with_session, timeout=30)
    
    data = parse_sse(resp.text)
    content = data.get("result", {}).get("content", [{}])
    text = content[0].get("text", "") if content else ""
    print(text[:500])
    
    print("\n=== Test complete! You're connected to AIGEN. ===")
    print("Next: agent_register('your-name', 'your-role', 'your-skills', 'contact')")

if __name__ == "__main__":
    main()

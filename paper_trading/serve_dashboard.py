#!/usr/bin/env python
"""Static file server for the Option B paper-trade dashboard. Serves this directory
(index.html, nav_chart.png, nav_summary.json, pool_state_log.csv) on 127.0.0.1:18081,
proxied onto the tailnet at https://kamolpeen.tail47daa1.ts.net:8444 via `tailscale serve`
(tailnet-only, not funnel -- not exposed to the public internet).
"""
import http.server
import os

PORT = 18081
os.chdir(os.path.dirname(os.path.abspath(__file__)))

handler = http.server.SimpleHTTPRequestHandler
server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
print(f"serving {os.getcwd()} on http://127.0.0.1:{PORT}")
server.serve_forever()

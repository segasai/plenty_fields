#!/bin/bash
# Run from project root
nohup python3 -m uvicorn arxiv_local.app.main:app --host 127.0.0.1 --port 8001 > server.log 2>&1 &
echo $! > server.pid

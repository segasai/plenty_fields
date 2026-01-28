#!/bin/bash
cd arxiv_local && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

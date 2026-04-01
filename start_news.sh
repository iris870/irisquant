#!/bin/bash
cd /root/irisquant
export PYTHONPATH=/root/irisquant
source /root/irisquant/venv/bin/activate
exec python agents/news.py

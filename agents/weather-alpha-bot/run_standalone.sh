#!/bin/bash
cd /root/weather-alpha
# 使用独立进程名 weather-alpha-bot，不与 irisquant 冲突
pm2 start venv/bin/python3 --name "weather-alpha-bot" -- main.py

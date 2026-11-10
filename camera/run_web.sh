#!/bin/bash
# 重启 Web 调试服务：camera/run_web.sh [额外参数]。在哪份代码里跑就用哪份的 .venv
cd "$(dirname "$0")/.." || exit 1
[ -f /tmp/camweb.pid ] && kill "$(cat /tmp/camweb.pid)" 2>/dev/null; sleep 1
setsid nohup .venv/bin/python -m camera.web --camera 2 --port 8000 --rotate180 "$@" > /tmp/camweb.log 2>&1 < /dev/null &
echo $! > /tmp/camweb.pid

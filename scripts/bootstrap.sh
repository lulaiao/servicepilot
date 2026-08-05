#!/bin/sh
set -eu

echo "ServicePilot environment check"
uname -a
python3 --version
git --version
docker --version 2>/dev/null || echo "Docker CLI: unavailable"
docker compose version 2>/dev/null || echo "Docker Compose: unavailable"
nvidia-smi 2>/dev/null || echo "NVIDIA runtime: unavailable"
df -h .


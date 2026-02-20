#!/bin/bash
# DGX Spark cleanup script — run this ON the DGX Spark server
# Steps 2-3 from the migration plan: OpenClaw removal + vllm-qwen cleanup
#
# Usage: ssh dgx 'bash -s' < scripts/dgx-cleanup.sh
#
set -euo pipefail

echo "=== Step 2-1: Backup needed files ==="
mkdir -p ~/projects/pydantic-assets
cp -v ~/openclaw-docker/gog ~/projects/pydantic-assets/ 2>/dev/null || echo "gog already backed up or not found"
cp -v ~/openclaw-docker/scripts/gogsafe ~/projects/pydantic-assets/ 2>/dev/null || echo "gogsafe already backed up or not found"
cp -v ~/openclaw-docker/.env ~/projects/pydantic-assets/ 2>/dev/null || echo ".env already backed up or not found"
echo "Backup done: ~/projects/pydantic-assets/"

echo ""
echo "=== Step 2-2: Stop OpenClaw containers ==="
docker compose -f ~/openclaw-docker/docker-compose.yml down 2>/dev/null || echo "OpenClaw compose already down"

echo ""
echo "=== Step 2-2: Remove OpenClaw images ==="
docker rmi openclaw-docker-openclaw:latest 2>/dev/null || true
docker rmi coollabsio/openclaw:latest 2>/dev/null || true
docker rmi vllm/vllm-openai:latest 2>/dev/null || true

echo ""
echo "=== Step 2-2: Prune dangling images ==="
docker image prune -f

echo ""
echo "=== Step 2-2: Remove volumes and network ==="
docker volume rm openclaw-docker_gogcli-config 2>/dev/null || true
docker volume rm openclaw-docker_searxng-data 2>/dev/null || true
docker network rm openclaw-docker_openclaw-net 2>/dev/null || true

echo ""
echo "=== Step 2-3: Remove OpenClaw files ==="
rm -rf ~/openclaw-docker
rm -rf ~/.openclaw
rm -rf ~/.clawhub
rm -rf ~/.config/clawhub
echo "OpenClaw files removed."

echo ""
echo "=== Step 3: Remove manual vllm-qwen container ==="
docker stop vllm-qwen 2>/dev/null || true
docker rm vllm-qwen 2>/dev/null || true
echo "vllm-qwen container removed. Image preserved for compose reuse."

echo ""
echo "=== Verification ==="
echo "Docker images:"
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
echo ""
echo "Preserved files:"
ls -la ~/projects/pydantic-assets/ 2>/dev/null || echo "pydantic-assets not found"
echo ""
echo "HuggingFace cache:"
ls ~/.cache/huggingface/hub/ 2>/dev/null || echo "No HF cache"
echo ""
echo "OpenClaw remnants (should be empty):"
ls ~/.openclaw ~/.clawhub ~/openclaw-docker 2>/dev/null || echo "None found - clean!"
echo ""
echo "=== Cleanup complete! ==="
echo "Next: cd ~/projects && rm -rf pydantic && git clone <repo> pydantic"

#!/bin/bash
# BenchMax Local Docker Image Builder (Bash, cross-platform)
set -euo pipefail

echo "============================================================"
echo "  BenchMax — Local Docker Image Builder (Bash)"
echo "============================================================"

DOCKER_DIR="backend/docker"
IMAGES=("benchmax-python:Dockerfile.python" "benchmax-node:Dockerfile.node" "benchmax-gcc:Dockerfile.gcc")
SUCCESSFUL=()
FAILED=()

if ! command -v docker &>/dev/null; then
    echo "[ERROR] Docker is not installed. Install Docker Desktop first." >&2
    exit 1
fi
if ! docker info &>/dev/null; then
    echo "[ERROR] Docker daemon is not running." >&2
    exit 1
fi
echo "[OK] Docker available"

for config in "${IMAGES[@]}"; do
    IFS=':' read -r name dockerfile <<< "$config"
    printf "\n--- Building %s ---\n" "$name"
    df_path="$DOCKER_DIR/$dockerfile"
    if [ ! -f "$df_path" ]; then
        echo "[WARN] $name: Dockerfile not found — skipping"
        FAILED+=("$name")
        continue
    fi
    docker build -f "$df_path" -t "$name:latest" "$DOCKER_DIR" 2>&1
    if [ $? -eq 0 ]; then
        echo "[OK] $name:latest built locally"
        SUCCESSFUL+=("$name")
    else
        echo "[ERROR] Build failed for $name" >&2
        FAILED+=("$name")
    fi
done

echo ""
if [ ${#SUCCESSFUL[@]} -gt 0 ]; then
    echo "============================================================"
    echo "[OK] Built ${#SUCCESSFUL[@]} image(s):"
    for img in "${SUCCESSFUL[@]}"; do
        size=$(docker image inspect "$img:latest" --format '{{.Size}}' 2>/dev/null || true)
        if [ -n "$size" ]; then
            mb=$((size / 1048576))
            echo "  ✓ $img ($mb MB)"
        else
            echo "  ✓ $img (local)"
        fi
    done
fi

if [ ${#FAILED[@]} -gt 0 ]; then
    echo ""
    echo "[WARN] Failed images:"
    for img in "${FAILED[@]}"; do
        echo "  ✗ $img"
    done
    echo ""
    echo "You can still run benchmarks — the executor falls back to public base images." >&2
    exit 1
fi

echo ""
echo "[OK] All local images built successfully!"

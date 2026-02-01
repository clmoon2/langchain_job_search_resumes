#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "applyEasy - Team Setup"
echo "============================================================"
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed."
    echo "        Install from https://docs.docker.com/get-docker/"
    exit 1
fi
echo "[OK] Docker found"

if ! command -v docker compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "[ERROR] Docker Compose is not available."
    echo "        Install from https://docs.docker.com/compose/install/"
    exit 1
fi
echo "[OK] Docker Compose found"

# Check for .env
if [ ! -f .env ]; then
    echo ""
    echo "[WARN] .env file not found."
    echo "       Copying .env.example to .env ..."
    cp .env.example .env
    echo "[OK] Created .env from template."
    echo ""
    echo "       Next steps:"
    echo "       1. Open .env in your editor"
    echo "       2. Fill in all credential values"
    echo "       3. Re-run this script"
    echo ""
    exit 1
else
    echo "[OK] .env file found"
fi

# Check required env vars
MISSING=0
while IFS='=' read -r key value; do
    # Skip comments and empty lines
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    # Skip commented-out option 2
    [[ "$key" =~ ^[[:space:]]*#.*$ ]] && continue
    # Check if value is still a placeholder
    if [[ "$value" =~ ^your- || "$value" =~ ^sk-proj-xxxx || "$value" =~ ^apify_api_xxxx || "$value" =~ ^ghp_xxxx || "$value" =~ ^GOCSPX-xxxx || "$value" =~ ^1//xxxx || "$value" =~ ^xxxx ]]; then
        echo "[WARN] $key still has placeholder value"
        MISSING=1
    fi
done < .env

if [ "$MISSING" -eq 1 ]; then
    echo ""
    echo "[WARN] Some credentials still have placeholder values."
    echo "       Edit .env and fill in real values before running."
    echo ""
fi

# Check for service-account.json
if [ ! -f service-account.json ]; then
    echo "[WARN] service-account.json not found."
    echo "       Copy your service account key file here, or set"
    echo "       GOOGLE_SERVICE_ACCOUNT_JSON as inline JSON in .env"
fi

# Check for resume_helper_fixed.txt
if [ ! -f resume_helper_fixed.txt ]; then
    echo "[WARN] resume_helper_fixed.txt not found."
    echo "       The pipeline needs this file to generate resumes."
fi

echo ""
echo "============================================================"
echo "Building Docker image..."
echo "============================================================"
docker compose build

echo ""
echo "============================================================"
echo "Setup complete."
echo "============================================================"
echo ""
echo "Run the pipeline:"
echo "  docker compose run --rm pipeline"
echo ""
echo "Run email outreach:"
echo "  docker compose run --rm email"
echo ""
echo "Open a dev shell:"
echo "  docker compose run --rm dev"
echo ""

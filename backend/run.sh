#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Sialdang Timelogs Backend (Local) ==="

# Check virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Checking dependencies..."
pip install -r requirements.txt

# Check .env
if [ ! -f ".env" ]; then
    echo "Creating default .env file..."
    cat <<EOF > .env
DB_HOST=127.0.0.1
DB_PORT=3306
DATABASE=timelogs
DB_USER=root
DB_PASSWORD=
JWT_SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(32))')
USER_DATA_ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
DEFAULT_TIMEZONE=Asia/Manila
EOF
    echo ".env created with local MySQL settings."
fi

echo "Starting backend server on http://localhost:8000 ..."
python main.py

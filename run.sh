#!/usr/bin/env bash
set -e

echo "=== Iniciando Instagram Stories Viewer & Auto-Downloader ==="

if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual Python..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "Instalando / verificando dependências..."
pip install -r requirements.txt

echo "Iniciando servidor em 0.0.0.0:8000..."
python app.py

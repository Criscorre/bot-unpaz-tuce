#!/bin/bash
# Bot TUCE — inicia Telegram bot (Python) + WhatsApp bridge (Node.js) juntos

echo "📦 Instalando dependencias Node.js..."
npm install

echo "🚀 Iniciando WhatsApp bridge (Node.js)..."
node whatsapp_bridge.js &

echo "🤖 Iniciando Bot Telegram (Python)..."
python main.py

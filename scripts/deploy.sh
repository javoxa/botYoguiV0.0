#!/bin/bash
# Script de deployment para producción

echo "🚀 Deploy UNSA Bot Escalable"

# 1. Instalar dependencias
echo "📦 Instalando dependencias..."
pip install -r requirements.txt

# 2. Configurar PostgreSQL
echo "🗄️  Configurando PostgreSQL..."
python3 scripts/setup_database_professional.py

# 3. Crear directorios necesarios
echo "📁 Creando estructura..."
mkdir -p logs cache database/migrations database/schema database/seeds

# 4. Iniciar servicios
echo "⚡ Iniciando servicios..."

# Servidor de inferencia (en background)
echo "🤖 Iniciando servidor de inferencia..."
nohup python3 backend/inference_server.py > logs/inference.log 2>&1 &
INFERENCE_PID=$!

# Bot (en foreground)
echo "🤖 Iniciando bot..."
python3 frontend/telegram_bot_scalable.py

# Limpiar al salir
trap "echo '🛑 Deteniendo servicios...'; kill $INFERENCE_PID 2>/dev/null" EXIT

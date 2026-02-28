#!/bin/bash

# 🐳 Script de testare rapidă Docker pentru CasehugBot

set -e

echo "🐳 CasehugBot - Docker Test Script"
echo "=================================="
echo ""

# Verificare Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker nu este instalat!"
    echo "💡 Instalează Docker de la: https://www.docker.com/get-started"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose nu este instalat!"
    echo "💡 Instalează Docker Compose"
    exit 1
fi

echo "✅ Docker: $(docker --version)"
echo "✅ Docker Compose: $(docker-compose --version)"
echo ""

# Verificare config.json
if [ ! -f "config.json" ]; then
    echo "⚠️ config.json nu există!"
    echo "💡 Creez din config.example.json..."
    
    if [ -f "config.example.json" ]; then
        cp config.example.json config.json
        echo "✅ config.json creat!"
        echo "⚠️ IMPORTANT: Editează config.json cu datele tale!"
        echo ""
        read -p "Apasă Enter după ce editezi config.json..."
    else
        echo "❌ config.example.json lipsește!"
        exit 1
    fi
fi

echo "✅ config.json există"
echo ""

# Verificare directoare
echo "📁 Creez directoare necesare..."
mkdir -p profiles
mkdir -p debug_output
echo "✅ Directoare create"
echo ""

# Build imagine Docker
echo "🔨 Build imagine Docker..."
echo "⏱️ Poate dura 2-5 minute prima dată..."
docker-compose build

if [ $? -eq 0 ]; then
    echo "✅ Imagine construită cu succes!"
else
    echo "❌ Eroare la build imagine!"
    exit 1
fi

echo ""
echo "=================================="
echo "🚀 Rulare bot în Docker..."
echo "=================================="
echo ""
echo "💡 Pentru a opri: Ctrl+C"
echo "💡 Pentru logs: docker-compose logs -f"
echo "💡 Pentru debug: verifică ./debug_output/"
echo ""

# Rulează containerul
docker-compose up

echo ""
echo "=================================="
echo "👋 Bot oprit"
echo "=================================="
echo ""
echo "📊 Pentru a rula în background:"
echo "   docker-compose up -d"
echo ""
echo "📋 Pentru a vedea logs:"
echo "   docker-compose logs -f"
echo ""
echo "🐛 Pentru debugging:"
echo "   ls debug_output/"
echo ""

#!/bin/bash

# Matrix Chat Backend Starter Script

echo "╔════════════════════════════════════════╗"
echo "║  🟢 MATRIX CHAT - Backend Starter      ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Navigate to backend directory
cd backend || {
    echo "❌ Error: backend directory not found"
    echo "Please run this script from the project root"
    exit 1
}

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 not found"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate || {
    # For Windows (if running via Git Bash or similar)
    source venv/Scripts/activate 2>/dev/null || {
        echo "❌ Error: Could not activate virtual environment"
        exit 1
    }
}

# Install requirements
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt || {
    echo "❌ Error: Failed to install dependencies"
    exit 1
}
echo "✓ Dependencies installed"

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created (using defaults)"
fi

# Check Ollama connection
echo ""
echo "🔍 Checking Ollama connection..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama is running at http://localhost:11434"
else
    echo "⚠️  WARNING: Could not reach Ollama at http://localhost:11434"
    echo "   Make sure Docker Ollama container is running:"
    echo "   docker run -d -p 11434:11434 ollama/ollama"
    echo ""
fi

# Start the server
echo ""
echo "🚀 Starting FastAPI server..."
echo "📍 Server will be available at http://localhost:8000"
echo "🏥 Health check: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python main.py

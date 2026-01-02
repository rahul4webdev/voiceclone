#!/bin/bash
# Local development setup script

set -e

echo "🎙️ VoiceClone - Local Development Setup"
echo "========================================"

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.10+ is required. Found: $python_version"
    exit 1
fi
echo "✅ Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate
echo "✅ Virtual environment activated"

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -e ".[dev]"

# Copy environment file
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your configuration"
fi

# Check Docker
if command -v docker &> /dev/null; then
    echo "✅ Docker is installed"

    # Start database and redis
    echo "🐳 Starting PostgreSQL and Redis..."
    docker compose up -d db redis

    # Wait for database
    echo "⏳ Waiting for database to be ready..."
    sleep 5
else
    echo "⚠️  Docker not found. Please install Docker for database."
    echo "   Or configure DATABASE_URL to point to an existing PostgreSQL instance."
fi

# Run migrations
echo "🔄 Running database migrations..."
alembic upgrade head || echo "⚠️  Migrations failed - database might not be ready"

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the development server:"
echo "  source venv/bin/activate"
echo "  uvicorn voiceclone.main:app --reload"
echo ""
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"

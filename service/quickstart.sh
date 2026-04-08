#!/bin/bash

echo "🚛 Transport Dispatch Service - Quick Start"
echo "==========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Copy .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ .env file created"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "🚀 Starting services..."
echo ""

# Build and start services
docker-compose up --build -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo "✅ Services are running!"
    echo ""
    echo "📍 Access points:"
    echo "   - API:       http://localhost:8000"
    echo "   - Dashboard: http://localhost:8501"
    echo "   - API Docs:  http://localhost:8000/docs"
    echo ""
    echo "📊 Quick test:"
    echo "   curl http://localhost:8000/health"
    echo ""
    echo "🛑 To stop services:"
    echo "   docker-compose down"
    echo ""
    echo "📝 To view logs:"
    echo "   docker-compose logs -f"
    echo ""
else
    echo "❌ Failed to start services. Check logs with: docker-compose logs"
    exit 1
fi

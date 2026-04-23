#!/bin/bash

# Simple script to launch Jenkins for the SWE6-Test project
echo "🚀 Starting Jenkins Dashboard..."

# 1. Try to start the containers
docker-compose up -d 2>/dev/null

if [ $? -ne 0 ]; then
    echo "❌ Error: Docker is not running!"
    echo "👉 Please open 'Docker Desktop' and try again."
    exit 1
fi

echo "✅ Jenkins is warming up (Port 8081)..."
echo "🔗 Access it here: http://localhost:8081"

# 2. On Mac, automatically open the browser after a short delay
if [[ "$OSTYPE" == "darwin"* ]]; then
    sleep 2
    open "http://localhost:8081"
fi

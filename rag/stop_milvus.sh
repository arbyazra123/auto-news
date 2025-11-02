#!/bin/bash
# Stop Milvus and related services

cd "$(dirname "$0")"

echo "Stopping Milvus services..."
docker-compose down

echo "Milvus services stopped"

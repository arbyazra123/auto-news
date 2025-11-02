#!/bin/bash
# Start Milvus and related services

cd "$(dirname "$0")"

echo "Starting Milvus services..."
docker-compose up -d

echo "Waiting for services to be ready..."
sleep 10

echo "Milvus services status:"
docker-compose ps

echo ""
echo "Milvus is ready!"
echo "  - Milvus: localhost:19530"
echo "  - Attu UI: http://localhost:1233"
echo "  - MinIO: localhost:9000"

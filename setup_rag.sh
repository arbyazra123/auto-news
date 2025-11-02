#!/bin/bash
# Quick setup script for RAG pipeline

set -e

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting RAG pipeline setup..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    log "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    log "Error: Python 3 is not installed"
    exit 1
fi

# Install Python dependencies
log "Installing Python dependencies..."
pip install -r requirements.txt

# Start Milvus
log "Starting Milvus services..."
cd rag
./start_milvus.sh
cd ..

log ""
log "Setup complete!"
log ""
log "Next steps:"
log "  1. Run the pipeline: bash prepare_news.sh"
log "  2. Analyze with Claude: bash run_daily_analysis.sh"
log "  3. View report: python3 serve_report.py"
log ""
log "Useful links:"
log "  - Report viewer: http://localhost:3131"
log "  - Milvus UI (Attu): http://localhost:1233"

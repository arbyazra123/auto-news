#!/bin/bash
# Step 1 & 2: Scrape news and preprocess

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Scraping news..."

python3 main.py

log "Preprocessing for Claude..."
python3 claude_preprocess.py

log "News preparation complete!"

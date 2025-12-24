#!/bin/bash
# News Pipeline: Scrape → Index → Query → Analyze

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Default max items
MAX_ITEMS=${MAX_ITEMS:-100}

log "Step 1: Scraping up to $MAX_ITEMS news articles..."
python3 src/scraper.py --max_items "$MAX_ITEMS"

if [ ! -f news.txt ]; then
    log "Error: news.txt not found after scraping"
    exit 1
fi

log "Step 2: Indexing articles into Milvus..."
python3 src/rag_indexer.py

log "Step 3: Querying most relevant articles via semantic search..."
python3 src/rag_query.py --top_k 50 --max_chars 2000 --days_back 1

if [ ! -f news_condensed.txt ]; then
    log "Error: news_condensed.txt not created"
    exit 1
fi

log "Pipeline complete! Top 50 relevant articles ready for analysis"

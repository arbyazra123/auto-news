#!/bin/bash
# RAG Pipeline: Scrape → Index → Query → Analyze

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Step 1: Scraping news articles (unlimited)..."
python3 main.py

if [ ! -f news.txt ]; then
    log "Error: news.txt not found after scraping"
    exit 1
fi

log "Step 2: Indexing articles into Milvus (RAG)..."
python3 rag_indexer.py

log "Step 3: Querying most relevant articles via semantic search..."
python3 rag_query.py --top_k 50 --max_chars 2000

if [ ! -f news_condensed.txt ]; then
    log "Error: news_condensed.txt not created"
    exit 1
fi

log "RAG pipeline complete! Top 50 relevant articles ready for analysis"

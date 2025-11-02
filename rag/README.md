# RAG Pipeline for Financial News Analysis

This directory contains the RAG (Retrieval-Augmented Generation) infrastructure for unlimited news scraping and intelligent filtering.

## Architecture

```
Scrape Unlimited Articles → Milvus Vector DB → Semantic Search → Claude Analysis
```

**Problem Solved:** Context window limitations when scraping hundreds of articles

**Solution:** Store everything in Milvus, retrieve only the most relevant articles for analysis

## Components

### Vector Database (Milvus)
- **etcd**: Metadata storage
- **minio**: Object storage for vectors
- **milvus-standalone**: Vector database engine
- **attu**: Web UI for Milvus (http://localhost:1233)

### Python Scripts
- `../rag_indexer.py`: Embed and store articles in Milvus
- `../rag_query.py`: Semantic search to retrieve relevant articles

## Setup Instructions

### 1. Start Milvus Services

```bash
cd rag
./start_milvus.sh
```

This will start:
- Milvus on port 19530
- Attu UI on http://localhost:1233
- MinIO on port 9000

### 2. Install Python Dependencies

```bash
cd ..
pip install -r requirements.txt
```

### 3. Run the RAG Pipeline

```bash
# Full pipeline (scrape → index → query → analyze)
bash prepare_news.sh

# Or run individually:
python3 main.py              # Scrape articles (unlimited)
python3 rag_indexer.py       # Index into Milvus
python3 rag_query.py         # Query top 50 relevant articles
```

## Usage

### Basic Workflow

```bash
# 1. Start Milvus
cd rag && ./start_milvus.sh && cd ..

# 2. Scrape and analyze
bash prepare_news.sh

# 3. Run Claude analysis
cat analysis_prompt.txt | claude -p --dangerously-skip-permissions
```

### Advanced Query Options

```bash
# Custom query with more results
python3 rag_query.py \
  --query "Banking sector news and interest rate changes" \
  --top_k 100 \
  --max_chars 3000

# Get top 30 articles focused on specific topics
python3 rag_query.py \
  --query "Stock price movements and trading volume analysis" \
  --top_k 30
```

### Explore Data with Attu UI

Visit http://localhost:1233 to:
- Browse stored articles
- View embeddings
- Run manual searches
- Monitor collection statistics

## How It Works

### 1. Indexing (rag_indexer.py)

```python
# Parses news.txt
# Generates embeddings using multilingual model
# Stores in Milvus with metadata:
#   - title, source, link, content
#   - 384-dim embedding vector
#   - timestamp
```

### 2. Querying (rag_query.py)

```python
# Default query: "today's stock market movements..."
# Embeds query → Searches Milvus → Returns top K similar articles
# Exports to news_condensed.txt (ready for Claude)
```

### 3. Embedding Model

**Model:** `paraphrase-multilingual-MiniLM-L12-v2`
- Supports Indonesian + English
- 384-dimensional embeddings
- Fast inference
- Good semantic understanding

## Benefits

1. **Unlimited Scraping**: No limit on how many articles you scrape
2. **Smart Filtering**: Semantic search finds what's relevant, not just keywords
3. **Context Window Friendly**: Only pass top N articles to Claude
4. **Historical Memory**: Query past articles anytime
5. **Scalable**: Handles thousands of articles efficiently

## Stopping Services

```bash
cd rag
./stop_milvus.sh
```

## Troubleshooting

### Milvus won't start
```bash
# Check Docker
docker ps

# View logs
cd rag
docker-compose logs milvus-standalone
```

### Connection refused
```bash
# Ensure Milvus is running
docker ps | grep milvus

# Restart services
cd rag
./stop_milvus.sh
./start_milvus.sh
```

### Out of memory
```bash
# Reduce top_k in query
python3 rag_query.py --top_k 30

# Or increase max_chars limit
python3 rag_query.py --max_chars 1500
```

## Storage Location

Milvus data is persisted in:
- `./volumes/etcd/` - Metadata
- `./volumes/minio/` - Vector data

These directories will be created automatically.

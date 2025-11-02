# RAG Pipeline Quick Start Guide

## One-Time Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start Milvus
cd rag && ./start_milvus.sh && cd ..

# 3. Test everything works
python3 test_rag.py
```

## Daily Usage

```bash
# Complete pipeline (scrape → index → query → analyze)
bash run_daily_analysis.sh

# View report
python3 serve_report.py
```

Then visit:
- **Report**: http://localhost:3131
- **Milvus UI**: http://localhost:1233

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Scrape    │────▶│   Milvus    │────▶│  Semantic   │────▶│   Claude    │
│ (unlimited) │     │  (RAG DB)   │     │   Search    │     │  Analysis   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
    main.py         rag_indexer.py       rag_query.py          claude -p
```

## Key Benefits

| Old Approach | RAG Approach |
|-------------|--------------|
| Limited by context window | Unlimited articles |
| Manual filtering | Smart semantic search |
| ~50 articles max | 500+ articles stored |
| Keyword matching | Meaning-based search |

## Customization

### Scrape more articles
Edit `main.py`:
```python
scrape_site(site, max_pages=5, max_item=30)  # More articles per site
```

### Change number of articles analyzed
```bash
python3 rag_query.py --top_k 100  # Analyze top 100 instead of 50
```

### Focus on specific topics
```bash
python3 rag_query.py --query "Banking sector and interest rate analysis" --top_k 30
```

## Troubleshooting

### "Connection refused" error
```bash
cd rag && ./start_milvus.sh && cd ..
```

### Test if everything works
```bash
python3 test_rag.py
```

### View Milvus logs
```bash
cd rag && docker-compose logs milvus-standalone
```

### Reset everything
```bash
cd rag
./stop_milvus.sh
rm -rf volumes/  # Deletes all stored data
./start_milvus.sh
cd ..
```

## Manual Step-by-Step

```bash
# 1. Scrape (unlimited)
python3 main.py

# 2. Index into Milvus
python3 rag_indexer.py

# 3. Query relevant articles
python3 rag_query.py --top_k 50

# 4. Analyze with Claude
cat analysis_prompt.txt | claude -p --dangerously-skip-permissions

# 5. View report
python3 serve_report.py
```

## Tips

- Attu UI (http://localhost:1233) lets you explore stored articles visually
- Articles persist in Milvus - you can query historical data anytime
- Adjust `max_chars` in rag_query.py to control article length in output
- Use semantic queries like "market trends" instead of keywords like "stock AND price"

## Stop Services

```bash
cd rag && ./stop_milvus.sh
```

Data is persisted in `rag/volumes/` - it won't be deleted when you stop services.

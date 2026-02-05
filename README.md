# Auto-News - Indonesian Stock Market Analysis with Semantic Search (MCP Support)

Automated Indonesian stock market news analysis using **Milvus Vector Search + AI Assistants via Model Context Protocol (MCP)**.

Connect any MCP-compatible AI assistant (Claude, or other LLMs) and ask: *"Show me the fundamental news today"* to get instant market insights!

## Table of Contents

- [Complete Workflow](#complete-workflow)
- [Quick Start](#quick-start)
  - [Installation](#installation)
  - [Option 1: Use with MCP-Compatible AI Assistants](#option-1-use-with-mcp-compatible-ai-assistants-recommended)
  - [Option 2: Manual CLI Usage](#option-2-manual-cli-usage)
  - [Option 3: REST API Usage](#option-3-rest-api-usage)
- [MCP Integration Details](#mcp-integration-details)
- [REST API Integration](#rest-api-integration)
- [Files Overview](#files-overview)
- [Manual Step-by-Step Usage](#manual-step-by-step-usage)
- [Web Server Features](#web-server-features)
- [Configuration](#configuration)
- [Daily Automation with Cron](#daily-automation-with-cron)
- [Troubleshooting](#troubleshooting)
- [Dependencies](#dependencies)
- [Example Output](#example-output)
- [Features](#features)
- [Future Enhancements](#future-enhancements)
- [Disclaimer](#disclaimer)

## Complete Workflow

```
1. Scrape unlimited news → 2. Index in Milvus → 3. Semantic search → 4. Claude analyzes or View on web
```

### Why Semantic Search?
**Problem:** Scraping 500+ articles exceeds Claude's context window (~200K tokens)

**Solution:** Store everything in Milvus vector DB, retrieve only the top 50 most relevant articles via semantic search, then let Claude analyze them

### Why MCP?
**Universal Integration:** MCP is an open protocol that works with any compatible AI assistant (Claude Desktop, Claude Code, and other MCP clients). Just ask your AI for news and it runs everything automatically!

## Quick Start

### Installation

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd auto-news

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start Milvus (vector database for semantic search)
docker-compose up -d
cd ..
```

### Option 1: Use with MCP-Compatible AI Assistants (Recommended!)

**Connect any MCP-compatible AI to your news pipeline:**

1. **Configure your MCP client** - Add to your MCP client's config file:
   - **Claude Code**: `~/.claude/claude_code_config.json`
   - **Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Other MCP clients**: Check your client's documentation for config location

   ```json
   {
   "mcpServers": {
      "auto-news": {
         "command": "python3",
         "args": ["/path/to/auto-news/src/mcp_server.py"]
      }
   }
   }
   ```

*Replace `/path/to/auto-news` with your actual project path. If using conda or venv, replace `python3` with your env path, e.g., `/Users/username/anaconda3/envs/env_name/bin/python3`*

2. **Restart your MCP client** (Claude Desktop, Claude Code, etc.)

3. **Ask your AI assistant:**
   - *"Show me the fundamental news today"* (scrapes 50 articles by default)
   - *"Get 200 Indonesian stock market articles"* (custom scraping limit)
   - *"Get Indonesian banking stocks news from last 3 days"*
   - *"Check if the Docker containers are running"*

That's it! Your AI assistant will automatically run the pipeline and analyze the news.

**Customization:** You can control how many articles to scrape by mentioning a number in your request, or the AI will use defaults (max_items=50, top_k=50).

**MCP Compatibility:** This server implements the [Model Context Protocol](https://modelcontextprotocol.io/) standard and works with any MCP-compatible client, not just Claude.

**Example Results:**

   ```md
   I'll get today's Indonesian stock market news for you.

   **KEY MARKET HIGHLIGHTS:**

   **IHSG:** Dropped 0.71% to 8,584.78 (Dec 23), opened weak today at 8,607 then slipped to 8,583

   **FOREIGN FLOW:** Net buy Rp2.5T in session 1 today - targeting mining/commodity stocks

   **TOP MOVERS:**
   - **BUMI:** -3.55% (heavy profit-taking after 14% jump Mon)
   - **INCO:** +12.39% (foreign accumulation Rp101B on Tue, +1.7% opening today)
   - **ANTM:** +74B foreign buy (nickel sector hot)
   - **BBCA:** -1.83% to Rp8,025 (pressure despite 3.73% div yield)

   **SENTIMENT:**
   - Santa Rally stalling - window dressing + profit-taking collide
   - Mining stocks magnets for foreign capital
   - IHSG target 9,000 still possible per IPOT but needs big-cap banking/infra surge
   - Investors cautious pre-Christmas holiday

   **TRADEABLE SETUPS:**
   - **INCO/ANTM:** Bandarmology strong, foreign accumulation continues
   - **Banks (BBCA/BMRI):** Undervalued on dividend play but profit-taking risk
   - **Infrastructure:** TLKM, BREN, TOWR seeing net buy flows

   **RISK:** Volume thin, profit-taking ahead of long holiday
   ```

### Option 2: Manual CLI Usage

```bash
# Run complete pipeline (scrape → index → semantic search)
bash prepare_news.sh

# Analyze with Claude Code CLI
bash run_daily_analysis.sh

# Start web server to view reports
python3 serve_report.py
```

Then open: **http://localhost:3131**

### Option 3: REST API Usage

**Start the unified API server** for programmatic access:

```bash
python src/unified_api_server.py
```

The API provides both **News Pipeline** and **Stock Analysis** endpoints:

**News Pipeline:**
- `POST /news/get` - Run news pipeline asynchronously
- `POST /news/get/sync` - Run news pipeline synchronously
- `GET /news/status` - Check pipeline status
- `GET /news/read` - Read condensed news report
- `GET /news/read/json` - Get report as JSON

**Stock Analysis:**
- `POST /api/stock/price` - Get current stock price & info
- `POST /api/stock/history` - Get historical OHLCV data
- `POST /api/stock/technicals` - Get technical indicators (RSI, MACD, MA, Bollinger Bands)
- `POST /api/stock/bandarmology` - Get bandarmology-style analysis (smart money flow)

**Interactive API documentation:** http://localhost:13051/docs

**For detailed API documentation, see:** [API_USAGE.md](API_USAGE.md)

### Useful Links
- **REST API Docs** (Swagger UI): http://localhost:13051/docs
- **Attu UI** (Milvus database explorer): http://localhost:1233
- **Web Report**: http://localhost:3131

## MCP Integration Details

The MCP server (`src/mcp_server.py`) provides 3 tools to any MCP-compatible AI assistant:

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_news` | Run full pipeline (scrape → index → query) | `max_items` (50), `query`, `top_k` (50), `days_back` (1), `max_chars` (2000) |
| `read_condensed_news` | Read existing news file | None |
| `check_docker_status` | Verify Milvus is running | None |

**`get_news` Parameters:**
- `max_items`: Total articles to scrape (default: 50)
- `query`: Semantic search query (default: market movements, price changes, etc.)
- `top_k`: Number of relevant articles to retrieve (default: 50)
- `days_back`: Filter articles from last N days (default: 1)
- `max_chars`: Max characters per article (default: 2000)

**How it works:**
```
Any MCP Client (Claude/etc) → MCP Protocol → mcp_server.py → Pipeline Scripts → Milvus → Results
```

The MCP server automatically uses your Python environment (conda/venv) to run the scripts.

**Learn more about MCP:** [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)

## REST API Integration

The unified API server (`src/unified_api_server.py`) provides a comprehensive REST API for both news pipeline management and stock market analysis.

### Quick Start

```bash
# Start the API server
python src/unified_api_server.py
```

The server runs on **http://localhost:13051** with interactive Swagger documentation at **/docs**.

### API Services

The API combines two major services:

#### 1. News Pipeline Service
Automated news scraping, indexing, and semantic search:

- **Run pipeline asynchronously** - `POST /news/get` (returns immediately, check status via `/news/status`)
- **Run pipeline synchronously** - `POST /news/get/sync` (waits for completion)
- **Check execution status** - `GET /news/status`
- **Read condensed report** - `GET /news/read` (plain text) or `GET /news/read/json` (JSON with metadata)

**Example:** Get 100 articles from the last 3 days:
```bash
curl -X POST http://localhost:13051/news/get \
  -H "Content-Type: application/json" \
  -d '{
    "max_items": 100,
    "days_back": 3,
    "top_k": 50
  }'
```

#### 2. Stock Analysis Service
Technical and fundamental analysis for Indonesian stocks (IDX):

- **Current price & info** - `POST /api/stock/price`
- **Historical OHLCV data** - `POST /api/stock/history`
- **Technical indicators** - `POST /api/stock/technicals` (RSI, MACD, Moving Averages, Bollinger Bands)
- **Bandarmology analysis** - `POST /api/stock/bandarmology` (smart money flow detection)

**Example:** Get technical analysis for BBCA:
```bash
curl -X POST http://localhost:13051/api/stock/technicals \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BBCA",
    "period": "6mo"
  }'
```

### Use Cases

- **Integrate with trading bots** - Automate news monitoring and technical analysis
- **Build dashboards** - Create custom web interfaces using the API
- **Schedule analysis** - Use cron jobs to trigger pipeline runs
- **Multi-client access** - Multiple applications can access the same pipeline
- **Mobile apps** - Build mobile interfaces for market monitoring

### Full API Documentation

For complete endpoint details, request/response schemas, and examples, see: **[API_USAGE.md](API_USAGE.md)**

## Files Overview

### Core Scripts
- **`src/mcp_server.py`** - MCP server (connects AI assistants to pipeline)
- **`src/unified_api_server.py`** - REST API server (news pipeline + stock analysis)
- **`src/helper/scraper.py`** - Scrapes financial news (unlimited articles)
- **`src/helper/rag_indexer.py`** - Embeds & stores articles in Milvus (with link deduplication)
- **`src/helper/rag_query.py`** - Semantic search for relevant articles
- **`src/helper/news_pipeline.py`** - End-to-end pipeline orchestrator
- **`src/stock_api/stock_api_server.py`** - Stock analysis service (technical & bandarmology)
- **`analysis_prompt.txt`** - Prompt template for AI analysis (CLI mode)
- **`serve_report.py`** - Web server to display reports

### Automation Scripts
- **`prepare_news.sh`** - News pipeline (scrape → index → semantic search)
- **`run_daily_analysis.sh`** - Complete automation + AI analysis

### Vector Database Infrastructure
- **`rag/docker-compose.yml`** - Milvus + etcd + MinIO + Attu
- **`rag/start_milvus.sh`** - Start vector database
- **`rag/stop_milvus.sh`** - Stop vector database

### Generated Files
- **`news.txt`** - Raw scraped articles (unlimited)
- **`news_condensed.txt`** - Top 50 relevant articles (from semantic search)
- **`daily_report.md`** - Final analysis report (generated by AI)

## Manual Step-by-Step Usage

### Step 1: Scrape News
```bash
python3 src/scraper.py --max_items 50
```
Creates `news.txt` with scraped articles (default: 50 articles).

**Options:**
- `--max_items N`: Maximum total articles to scrape (default: 50)
- `--output FILE`: Output file path (default: news.txt)

### Step 2: Index in Milvus
```bash
python3 src/rag_indexer.py
```
Embeds articles and stores in Milvus vector database.

### Step 3: Semantic Search
```bash
python3 src/rag_query.py --top_k 50 --max_chars 2000
```
Retrieves top 50 most relevant articles → `news_condensed.txt`

**Advanced queries:**
```bash
# Focus on specific topics
python3 src/rag_query.py --query "Banking sector and interest rates" --top_k 30

# Get more articles
python3 src/rag_query.py --top_k 50 --max_chars 1500
```

### Step 4: Run AI Analysis (if using CLI)
```bash
cat analysis_prompt.txt | claude -p --dangerously-skip-permissions
```
Your AI assistant analyzes top articles and generates `daily_report.md`.

### Step 5: View Report on Web
```bash
python3 src/serve_report.py
```
Visit: http://localhost:3131

## Web Server Features

- Auto-converts Markdown to HTML
- Clean, responsive UI
- Auto-refresh every 5 minutes
- Manual refresh button
- Serves on `0.0.0.0:3131` (accessible from network)

## Configuration

### Change Web Server Port
Edit `serve_report.py`:
```python
PORT = 3131  # Change this
```

### Scraping Sources
Edit `scraper.py` - `get_sites()` function to add/remove sources.

### Analysis Style
Edit `analysis_prompt.txt` to customize your AI's analysis approach.

## Daily Automation with Cron

Run analysis automatically every day at 9 AM:

```bash
# Edit crontab
crontab -e

# Add this line:
0 9 * * * cd /path/to/auto-news && bash run_daily_analysis.sh >> cron.log 2>&1
```

Then keep the web server running:
```bash
# Run in background with nohup
nohup python3 serve_report.py > server.log 2>&1 &
```

## Troubleshooting

### MCP: "Cannot run news pipeline: Required Docker containers are not running"
Start Milvus containers:
```bash
cd rag
docker-compose up -d

# Verify
docker ps | grep -E "milvus|etcd|minio"
```

### MCP: Server not connecting to AI client
1. Check config path is correct:
   ```bash
   ls -la /path/to/auto-news/src/mcp_server.py
   ```
2. Make script executable:
   ```bash
   chmod +x src/mcp_server.py
   ```
3. Verify MCP package installed:
   ```bash
   pip list | grep mcp
   ```
4. Restart your MCP client (Claude Desktop/Code or other)

### "daily_report.md not found"
Run the analysis first:
```bash
bash run_daily_analysis.sh
```

### AI CLI not responding
Make sure your AI CLI is installed and accessible:
```bash
which claude  # or your AI's command
```

### Port 3131 already in use
Change port in `serve_report.py` or kill existing process:
```bash
lsof -ti:3131 | xargs kill -9
```

### API: Port 13051 already in use
Change port in `src/unified_api_server.py` or kill existing process:
```bash
lsof -ti:13051 | xargs kill -9
```

### API: "Stock data not available" or Yahoo Finance errors
Some Indonesian stocks may have different ticker formats on Yahoo Finance:
- IDX format: `BBCA`
- Yahoo Finance format: `BBCA.JK` (automatically appended by the API)

If issues persist:
1. Verify stock symbol is correct (check IDX website)
2. Try a different time period (some stocks have limited historical data)
3. Check internet connectivity (API needs to access Yahoo Finance)

### API: Milvus connection errors
Ensure Docker containers are running:
```bash
docker ps | grep -E "milvus|etcd|minio"

# If not running, start them:
cd rag
docker-compose up -d
```

## Dependencies

See `requirements.txt` for full list:

```bash
pip install -r requirements.txt
```

Key packages:
- `requests`, `beautifulsoup4` - Web scraping
- `pymilvus` - Vector database client
- `sentence-transformers` - Multilingual embeddings
- `torch` - Deep learning backend
- `mcp` - Model Context Protocol SDK
- `fastapi`, `uvicorn` - REST API server
- `yfinance` - Stock market data from Yahoo Finance
- `pandas`, `numpy` - Data analysis
- `ta` - Technical analysis indicators

## Example Output

The generated `daily_report.md` includes:
- Market overview & sentiment
- Most mentioned stocks
- Price movements & catalysts
- Top 3 actionable recommendations
- Individual article analysis

## Features

### Technical Analysis Integration ✅ **IMPLEMENTED**

The system now includes comprehensive technical analysis via the **REST API**:

- **Data Source**: Real-time stock data from Yahoo Finance API
- **Technical Indicators Available**:
  - Moving averages (SMA 20/50, EMA 12/26)
  - RSI (Relative Strength Index)
  - MACD (Moving Average Convergence Divergence)
  - Bollinger Bands
  - Volume analysis (OBV, ADL, VPT)
  - Money Flow Index (MFI)
  - Average True Range (ATR)

- **Bandarmology Analysis**: Smart money flow detection with:
  - Accumulation/Distribution phases
  - Volume pattern recognition
  - Price structure analysis
  - Breakout triggers
  - Risk management levels (stop loss, take profit)

**Access via REST API:**
```bash
# Get technical indicators
curl -X POST http://localhost:13051/api/stock/technicals \
  -d '{"symbol": "BBCA", "period": "6mo"}'

# Get bandarmology analysis
curl -X POST http://localhost:13051/api/stock/bandarmology \
  -d '{"symbol": "BBCA", "period": "6mo"}'
```

See [API_USAGE.md](API_USAGE.md) for complete documentation.

## Future Enhancements

### Planned Features

- **Unified Analysis Endpoint**: Combine fundamental news + technical indicators into a single endpoint
  - Cross-reference fundamental news with technical signals
  - Identify stocks where both analyses align (strong buy/sell signals)
  - Flag divergences (e.g., positive news but bearish technicals)
  - Generate confidence scores based on multi-factor agreement
  - Example: `POST /api/stock/unified_analysis` → Combined recommendation

- **MCP Integration for Stock Analysis**: Add stock analysis tools to MCP server
  - `get_stock_price` - Query stock prices from AI assistants
  - `get_technical_analysis` - Get technical indicators via AI
  - `get_bandarmology` - Get smart money flow analysis via AI

- **Multi-language support**: Scrape English financial news sources
- **Sentiment analysis**: Add NLP sentiment scoring to news articles
- **Alert system**: WhatsApp/Telegram notifications for critical market events
- **Portfolio tracking**: Monitor your holdings against news/technical signals
- **Backtesting**: Test strategy performance against historical data
- **Real-time updates**: WebSocket integration for live market data
- **Advanced deduplication**: Beyond link-based deduplication, add content similarity detection

**Contributions welcome!** Feel free to implement any of these features.

## Disclaimer

**Investment Risk:** This tool is for educational and informational purposes only. Always conduct your own research before making investment decisions.

**Web Scraping:** This tool scrapes publicly available news for personal use. Please:
- Respect the terms of service of scraped websites
- Use responsibly and avoid excessive server load
- Not use for commercial redistribution of scraped content
- Check `robots.txt` policies of target websites

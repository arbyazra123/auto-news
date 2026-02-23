# Auto-News - Indonesian Stock Market Analysis Platform

Comprehensive Indonesian stock market analysis platform with **News Pipeline + Technical Analysis + MCP Integration** - all running in Docker containers.

**Features:**
- Automated news scraping and semantic search (Milvus vector database)
- Technical analysis API (RSI, MACD, Bollinger Bands, Smart Money Flow)
- Trading strategy screening (PREOPEN, BPJS, BSJP, Day Trade setups)
- MCP server for AI assistant integration (Claude Desktop/Code)
- RESTful API for programmatic access

Connect any MCP-compatible AI assistant (Claude, or other LLMs) and ask: *"Show me today's Indonesian stock market news"* to get instant market insights!

## What's New

### Major Updates

**🐳 Unified Docker Architecture**
- All services now run in containers via `docker-compose.yml` at project root
- `idx-stock-api` container - Internal API for data processing (port 13052)
- `idx-report-server` container - Public web UI for reports (port 3131, read-only)
- Persistent data volumes for seamless updates and restarts
- No more manual dependency installation!

**🚀 Comprehensive Stock API**
- **20+ REST endpoints** for news, stock data, technical analysis, and screening
- **Port 13052** - New unified API server (replaces old port 13051)
- Technical indicators: RSI, MACD, Bollinger Bands, Volume analysis
- Bandarmology/smart money flow detection
- Trading strategy screening (PREOPEN, BPJS, BSJP, Day Trade)
- Market context endpoints (global sentiment, trading time, stock lists)

**🔌 Enhanced MCP Integration**
- MCP server now runs **inside Docker** via `docker exec`
- Shares same `/app/data` volume as FastAPI server
- 5 MCP tools for news pipeline management
- Seamless integration with Claude Desktop/Code

**🔐 Security Features**
- Optional `CLAUDE_SECRET_KEY` authentication for sensitive endpoints
- Localhost/Docker network IP whitelisting for `/api/news/analyze` (openclaw integration)
- Claude CLI credentials stored in persistent volumes
- Environment-based configuration via `.env` file

**📁 Reorganized Project Structure**
- Pipeline scripts moved to `src/helper/`
- Stock API code in `src/stock_api/`
- Data persistence in `volumes/` directory
- Docker-compose at project root (no more `rag/` subdirectory)

**📋 For detailed migration guide from older versions, see the changelog at the end of this README.**

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

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                        Docker Compose Stack                            │
├───────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐  ┌───────────────────────┐  ┌────────────────┐ │
│  │  Milvus Stack    │  │  Stock API Container  │  │ Report Server  │ │
│  │  ─────────────   │  │  (idx-stock-api)      │  │ (public web)   │ │
│  │  • Milvus DB     │←─┤  ─────────────────    │  │ ──────────────  │ │
│  │  • etcd          │  │  • FastAPI (13052)    │  │ • Web UI       │ │
│  │  • MinIO         │  │    [Internal Only]    │  │   (port 3131)  │ │
│  │  • Attu UI       │  │  • News Pipeline      │  │ • Read-only    │ │
│  └──────────────────┘  │  • Technical APIs     │  │   /app/data    │ │
│                         │  • MCP Server         │←─┤ • Auto-refresh │ │
│                         └───────────────────────┘  └────────────────┘ │
│                                                                         │
│                         volumes/news_data/ (shared)                    │
│                         ├─ news.txt                                    │
│                         ├─ news_condensed.txt                          │
│                         └─ daily_report.md  ←─────(read-only)          │
└───────────────────────────────────────────────────────────────────────┘
                                    ↑
                    ┌───────────────┼───────────────┐
                    │               │               │
             ┌──────▼─────┐  ┌──────▼─────┐  ┌──────▼─────┐
             │   MCP      │  │  REST API  │  │  Browser   │
             │  Clients   │  │   Clients  │  │  (Public)  │
             │  (Claude)  │  │  (curl/app)│  │  :3131     │
             └────────────┘  └────────────┘  └────────────┘
```

### Complete Workflow

**News Pipeline:**
```
1. Scrape unlimited articles → 2. Index in Milvus → 3. Semantic search → 4. AI analysis
```

**Stock Analysis:**
```
1. Fetch OHLCV from Yahoo Finance → 2. Calculate indicators → 3. Generate signals → 4. Return analysis
```

### Why This Architecture?

**Containerized:** All services run in Docker - consistent environment, easy deployment

**Security-First:** Stock API (port 13052) stays internal, only report server (port 3131) exposed publicly

**Separation of Concerns:**
- `idx-stock-api` - Internal API for data processing (news + stock analysis)
- `idx-report-server` - Public web server with read-only access to reports

**Semantic Search:** Milvus vector database handles 500+ articles efficiently (no token limits)

**MCP Integration:** Connect AI assistants directly to your stock analysis infrastructure

## Quick Start

### Installation

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd auto-news

# 2. Create Docker network (required for inter-container communication)
docker network create tunnel

# 3. (Optional) Configure security for Claude analysis endpoint
cp .env.example .env
# Edit .env and set CLAUDE_SECRET_KEY for production use

# 4. Start all services (Milvus + Stock API)
docker-compose up -d

# 5. Verify services are running
docker ps
# You should see: etcd, minio, milvus-standalone, attu, idx-stock-api, idx-report-server

# 6. Check services health
curl http://localhost:13052/        # Stock API (internal)
curl http://localhost:3131/         # Report Server (public web UI)

# 7. (Optional) Configure Claude CLI for /api/news/analyze endpoint
# This allows the API to analyze news using Claude
docker exec -it idx-stock-api su appuser -c "claude /login"
# Follow the prompts to authenticate with your Claude account
```

**Service Ports:**
- **13052** - Stock API (keep internal, for API/MCP access only)
- **3131** - Report Server (safe to expose publicly, read-only web UI)
- **19530** - Milvus (internal only)
- **1233** - Attu UI (optional, for database management)

**Notes:**
- The Stock API container includes all dependencies (Python packages, embedding models, etc.) - no need to install anything locally unless you want to run scripts outside Docker.
- The Report Server is a minimal (~50MB) Alpine container with read-only access to reports.
- Claude CLI configuration is optional and only needed if you want to use the `/api/news/analyze` endpoint for automated AI analysis.

### Option 1: Use with MCP-Compatible AI Assistants (Recommended!)

**Connect any MCP-compatible AI to your news pipeline - now running inside Docker!**

1. **Ensure Docker containers are running:**
   ```bash
   docker ps | grep idx-stock-api
   # Should show the stock-api container
   ```

2. **Configure your MCP client** - Add to your MCP client's config file:
   - **Claude Code**: `~/.claude/claude_code_config.json`
   - **Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Other MCP clients**: Check your client's documentation for config location

   ```json
   {
     "mcpServers": {
       "stock-news": {
         "type": "stdio",
         "command": "docker",
         "args": ["exec", "-i", "idx-stock-api", "python3", "/app/mcp_server.py"]
       }
     }
   }
   ```

   **What this does:** Uses `docker exec` to run the MCP server inside the `idx-stock-api` container, allowing it to share the same data volume (`/app/data`) and network as the FastAPI server.

3. **Restart your MCP client** (Claude Desktop, Claude Code, etc.)

4. **Ask your AI assistant:**
   - *"Show me today's Indonesian stock market news"*
   - *"Get the latest news and check the status"*
   - *"Read the condensed news report"*
   - *"Check which files already exist in the data folder"*

That's it! Your AI assistant will automatically call the MCP tools which communicate with the FastAPI server running in Docker.

**Available MCP Tools:**
- `get_news_status` - Check pipeline status
- `run_news_pipeline_async` - Start news scraping in background
- `run_news_pipeline_sync` - Run news scraping synchronously
- `check_existing_files` - See which reports already exist
- `read_news_report` - Read condensed news output

**MCP Compatibility:** This server implements the [Model Context Protocol](https://modelcontextprotocol.io/) standard and works with any MCP-compatible client, not just Claude.

**Example Results (Simplified):**

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

# View report in browser (report server is already running!)
open http://localhost:3131
```

The report server container automatically displays `volumes/news_data/daily_report.md` when you visit **http://localhost:3131**

### Option 3: REST API Usage

**The Stock API server runs automatically in Docker** (no manual startup needed!):

```bash
# API is already running on port 13052
curl http://localhost:13052/

# View interactive API documentation
open http://localhost:13052/docs
```

The API provides comprehensive **News Pipeline + Stock Analysis + Screening** endpoints:

**News Pipeline Endpoints:**
- `POST /api/news/get` - Run news pipeline asynchronously (returns immediately)
- `POST /api/news/get/sync` - Run news pipeline synchronously (waits for completion)
- `GET /api/news/status` - Check pipeline status
- `GET /api/news/read` - Read condensed news report (plain text)
- `GET /api/news/read/json` - Get report as JSON with metadata
- `GET /api/news/analyze` - Analyze news with Claude CLI (localhost-only, for openclaw integration)
- `GET /api/news/check_files` - Check which output files exist

**Note on `/api/news/analyze`:** This endpoint is designed for local orchestration and openclaw channel integration. It requires Claude CLI authentication inside the container and only accepts requests from localhost/Docker network by default. See [Security & Claude CLI Integration](#security--claude-cli-integration) for setup instructions.

**Stock Data & Analysis Endpoints:**
- `POST /api/stock/price` - Get current stock price & info
- `POST /api/stock/history` - Get historical OHLCV data
- `POST /api/stock/technicals` - Get technical indicators (RSI, MACD, MA, Bollinger Bands)
- `POST /api/stock/bandarmology` - Get bandarmology/smart money flow analysis
- `POST /api/stock/fundamentals` - Get fundamental data (P/E, P/B, ROE, etc.)
- `POST /api/stock/mandiri-report` - Generate Mandiri Sekuritas-style report

**Market Context Endpoints:**
- `POST /api/market/global` - Check global market sentiment (S&P500, Nikkei, commodities)
- `POST /api/market/time-context` - Get WIB time & trading session context
- `POST /api/market/stock-list` - Get LQ45/IDX30 stock lists

**Trading Strategy Screening Endpoints:**
- `POST /api/screen/preopen` - Screen for PRE-OPEN setups (execute 08:45-08:58 WIB)
- `POST /api/screen/bpjs` - Screen for BPJS (Beli Pagi Jual Sore) setups
- `POST /api/screen/bsjp` - Screen for BSJP (Beli Sore Jual Pagi) setups
- `POST /api/screen/day-trade` - Screen for day trade opportunities (Mandiri-style)

**Example API Call:**
```bash
# Get technical analysis for BBCA
curl -X POST http://localhost:13052/api/stock/technicals \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BBCA", "period": "6mo"}'

# Run news pipeline
curl -X POST http://localhost:13052/api/news/get \
  -H "Content-Type: application/json" \
  -d '{"max_items": 100, "top_k": 50}'
```

### Useful Links
- **Daily Report Web UI**: http://localhost:3131 (safe for public access)
- **Stock API Docs** (Swagger UI): http://localhost:13052/docs (keep internal)
- **Attu UI** (Milvus database explorer): http://localhost:1233 (optional)

## MCP Integration Details

The MCP server (`src/stock_api/mcp_server.py`) runs **inside the Docker container** and provides 5 tools for managing the news pipeline:

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_news_status` | Check pipeline status | None |
| `run_news_pipeline_async` | Start pipeline in background | `max_items` (100), `query`, `top_k` (30), `days_back` (2), `max_chars` (2000), `skip_scrape`, `skip_index` |
| `run_news_pipeline_sync` | Run pipeline synchronously | Same as async |
| `check_existing_files` | Check which reports exist | None |
| `read_news_report` | Read condensed news output | `file` (news_condensed.txt) |

**Key Parameters:**
- `max_items`: Total articles to scrape (default: 100)
- `query`: Semantic search query (default: market movements, price changes, trading analysis)
- `top_k`: Number of relevant articles to retrieve (default: 30)
- `days_back`: Filter articles from last N days (default: 2)
- `max_chars`: Max characters per article (default: 2000)
- `skip_scrape`: Skip scraping if already done (default: false)
- `skip_index`: Skip indexing if already done (default: false)

**Architecture:**
```
MCP Client (Claude) → docker exec → mcp_server.py → HTTP calls → stock_api_server.py → Pipeline/Milvus
```

**Why Docker exec?**
- Shares the same `/app/data` volume as the FastAPI server
- No path issues - everything is containerized
- Consistent environment regardless of host OS

**Learn more about MCP:** [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)

## REST API Integration

The Stock API server (`src/stock_api/stock_api_server.py`) runs automatically in Docker and provides a comprehensive REST API.

### Quick Start

```bash
# API is already running! No manual start needed.
# Just verify it's up:
curl http://localhost:13052/

# Access interactive documentation:
open http://localhost:13052/docs
```

The server runs on **http://localhost:13052** with interactive Swagger documentation at **/docs**.

### API Services

The API provides three major services:

#### 1. News Pipeline Service
Automated news scraping, indexing, and semantic search:

- **Run pipeline asynchronously** - `POST /api/news/get` (returns immediately, check status via `/api/news/status`)
- **Run pipeline synchronously** - `POST /api/news/get/sync` (waits for completion)
- **Check execution status** - `GET /api/news/status`
- **Read condensed report** - `GET /api/news/read` (plain text) or `GET /api/news/read/json` (JSON with metadata)
- **Analyze with Claude** - `GET /api/news/analyze` (requires Claude CLI credentials)
- **Check existing files** - `GET /api/news/check_files`

**Example:** Get 100 articles from the last 3 days:
```bash
curl -X POST http://localhost:13052/api/news/get \
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
- **Fundamentals** - `POST /api/stock/fundamentals` (P/E, P/B, ROE, debt ratios, etc.)
- **Mandiri-style report** - `POST /api/stock/mandiri-report` (comprehensive analysis report)

**Example:** Get technical analysis for BBCA:
```bash
curl -X POST http://localhost:13052/api/stock/technicals \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BBCA",
    "period": "6mo"
  }'
```

#### 3. Trading Strategy Screening
Screen for specific trading setups across LQ45/IDX30:

- **PREOPEN setups** - `POST /api/screen/preopen` (analyze overnight, execute 08:45-08:58 WIB)
- **BPJS setups** - `POST /api/screen/bpjs` (buy morning, sell afternoon - same day)
- **BSJP setups** - `POST /api/screen/bsjp` (buy afternoon, sell next morning)
- **Day trade setups** - `POST /api/screen/day-trade` (Mandiri Sekuritas-style screening)

**Example:** Screen for day trade opportunities:
```bash
curl -X POST http://localhost:13052/api/screen/day-trade \
  -H "Content-Type: application/json" \
  -d '{
    "stock_index": "LQ45",
    "limit": 10,
    "mode": "mandiri"
  }'
```

### Use Cases

- **Integrate with trading bots** - Automate news monitoring and technical analysis
- **Build dashboards** - Create custom web interfaces using the API
- **Schedule analysis** - Use cron jobs to trigger pipeline runs
- **Multi-client access** - Multiple applications can access the same pipeline
- **Mobile apps** - Build mobile interfaces for market monitoring
- **Strategy backtesting** - Historical data + technical indicators for testing

### Security & Claude CLI Integration

#### Claude CLI Setup (for /api/news/analyze endpoint)

The `/api/news/analyze` endpoint allows automated AI analysis of news using the Claude CLI. To use this feature:

**Step 1: Authenticate Claude CLI inside container**
```bash
# Login to Claude from inside the container
docker exec -it idx-stock-api su appuser -c "claude /login"

# Follow the interactive prompts to authenticate
# Your credentials will be stored in volumes/claude_config/
```

**Step 2: Test the endpoint**
```bash
# Analyze news (from localhost)
curl http://localhost:13052/api/news/analyze

# The API will read news_condensed.txt and generate daily_report.md
```

#### Security Model

The `/api/news/analyze` endpoint is designed for **local orchestration and openclaw channel integration**, which is why it has stricter security:

**Default Security (No CLAUDE_SECRET_KEY set):**
- ✅ Accepts requests from: `localhost`, `127.0.0.1`, `::1`, Docker internal network (`172.*`, `192.168.*`)
- ❌ Rejects requests from: External/public IPs
- **Use case:** Local automation, cron jobs, openclaw channel integration on same machine

**Optional Enhanced Security (CLAUDE_SECRET_KEY set):**
```bash
# Set in .env file
CLAUDE_SECRET_KEY=your-secret-key-here

# Restart container to apply
docker-compose restart stock-api

# Then call with secret key header:
curl -X GET http://localhost:13052/api/news/analyze \
  -H "X-Secret-Key: your-secret-key-here"
```

**Why this security model?**
- The `/api/news/analyze` endpoint uses your personal Claude CLI credentials
- Designed for **openclaw channel integration** (local AI orchestration)
- Prevents unauthorized external access to your Claude account
- Other endpoints (stock data, screening) are open for broader integration

**Note:** If you need external access to AI analysis, consider:
1. Using MCP integration instead (secure by design)
2. Setting up a reverse proxy with proper authentication
3. Using the endpoint only for local cron jobs/automation

## Files Overview

### Docker Infrastructure
- **`docker-compose.yml`** - Complete stack (Milvus + Stock API + Report Server)
- **`src/stock_api/Dockerfile`** - Stock API container definition
- **`Dockerfile.report`** - Minimal report server container (~50MB Alpine)
- **`src/stock_api/entrypoint.sh`** - Container initialization script
- **`.env.example`** - Security configuration template
- **`.dockerignore`** - Optimizes report server build context

### Core API Server
- **`src/stock_api/stock_api_server.py`** - Main FastAPI server (all endpoints)
  - News pipeline management
  - Stock data & technical analysis
  - Trading strategy screening
  - Market context endpoints
- **`src/stock_api/mcp_server.py`** - MCP server for AI assistants (runs inside Docker)

### Pipeline Scripts (in Container)
- **`src/helper/scraper.py`** - Scrapes Indonesian financial news
- **`src/helper/rag_indexer.py`** - Embeds & indexes articles in Milvus
- **`src/helper/rag_query.py`** - Semantic search for relevant articles
- **`src/helper/news_pipeline.py`** - End-to-end pipeline orchestrator
- **`src/helper/serve_report.py`** - Web server to display markdown reports

### Automation Scripts (Host)
- **`prepare_news.sh`** - News pipeline wrapper (scrape → index → semantic search)
- **`run_daily_analysis.sh`** - Complete automation + AI analysis
- **`analysis_prompt.txt`** - Prompt template for AI analysis (CLI mode)

### Data Volumes (Persisted)
- **`volumes/news_data/`** - Generated files (news.txt, news_condensed.txt, daily_report.md)
- **`volumes/claude_config/`** - Claude CLI credentials mount point
- **`volumes/milvus/`** - Milvus database storage
- **`volumes/etcd/`** - etcd configuration storage
- **`volumes/minio/`** - MinIO object storage

### Generated Files (in volumes/news_data/)
- **`news.txt`** - Raw scraped articles
- **`news_condensed.txt`** - Top relevant articles (from semantic search)
- **`daily_report.md`** - Final analysis report (generated by AI)

## Manual Step-by-Step Usage

You can interact with the system in multiple ways:

### Method 1: Using REST API (Recommended)

```bash
# Step 1: Run news pipeline via API
curl -X POST http://localhost:13052/api/news/get/sync \
  -H "Content-Type: application/json" \
  -d '{"max_items": 100, "top_k": 50}'

# Step 2: Read condensed news
curl http://localhost:13052/api/news/read

# Step 3: (Optional) Analyze with Claude
curl http://localhost:13052/api/news/analyze
```

### Method 2: Using Host Scripts

```bash
# Step 1: Run complete pipeline
bash prepare_news.sh

# Step 2: Analyze with Claude CLI
bash run_daily_analysis.sh

# Step 3: View report in browser (server already running!)
open http://localhost:3131
# The report server container automatically serves daily_report.md
```

### Method 3: Using Docker Exec (Direct Container Access)

```bash
# Step 1: Scrape news inside container
docker exec -it idx-stock-api python3 /app/helper/scraper.py --max_items 100

# Step 2: Index in Milvus
docker exec -it idx-stock-api python3 /app/helper/rag_indexer.py

# Step 3: Semantic search
docker exec -it idx-stock-api python3 /app/helper/rag_query.py --top_k 50

# Step 4: View generated files
docker exec -it idx-stock-api ls -lh /app/data/
docker exec -it idx-stock-api cat /app/data/news_condensed.txt
```

### Method 4: Using MCP Tools

Just ask your MCP-connected AI assistant:
```
"Get today's Indonesian stock market news"
```

The AI will automatically run the appropriate MCP tools!

## Report Server Features

The `idx-report-server` container provides a lightweight web UI for viewing daily market reports:

**Features:**
- Auto-converts Markdown to HTML with syntax highlighting
- Clean, responsive UI optimized for readability
- Auto-refresh every 5 minutes
- Manual refresh button
- Shows report generation timestamp (Jakarta timezone)
- Read-only access to `/app/data` volume (secure)
- Serves on `0.0.0.0:3131` (accessible from network)
- Minimal footprint (~50MB Alpine-based container)

**Security:**
- No write access to data volume (mounted read-only)
- Safe to expose publicly - only displays reports
- No API keys or sensitive data exposed
- Independent from Stock API (separation of concerns)

**Access:**
- Local: http://localhost:3131
- Network: http://your-server-ip:3131
- Can be reverse-proxied through Nginx/Caddy for HTTPS

## Configuration

### Environment Variables

Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

**Available Options:**
- `CLAUDE_SECRET_KEY` - Optional secret key for `/api/news/analyze` endpoint security (for openclaw integration)
  - If not set: Only accepts localhost/Docker network requests
  - If set: Requires `X-Secret-Key` header for all requests
- `MILVUS_HOST` - Milvus server hostname (default: milvus-standalone)
- `MILVUS_PORT` - Milvus server port (default: 19530)

### Claude CLI Configuration

To enable the `/api/news/analyze` endpoint (for automated AI analysis):

```bash
# 1. Login to Claude CLI inside container
docker exec -it idx-stock-api su appuser -c "claude /login"

# 2. Verify credentials are saved
docker exec -it idx-stock-api su appuser -c "ls -la /home/appuser/.claude"

# 3. Test the analyze endpoint
curl http://localhost:13052/api/news/analyze
```

**What gets stored:**
- Claude credentials are stored in `volumes/claude_config/` on your host
- This directory is mounted to `/home/appuser/.claude` inside the container
- Credentials persist across container restarts

**Use cases:**
- Local cron jobs for daily automated analysis
- Openclaw channel integration for AI-powered market reports
- Automated report generation workflows

### Change API Server Port

Edit `docker-compose.yml`:
```yaml
services:
  stock-api:
    ports:
      - "13052:13052"  # Change host port (left side)
```

Then restart: `docker-compose up -d`

### Scraping Sources

Edit `src/helper/scraper.py` - modify the `get_sites()` function to add/remove news sources.

To update inside Docker:
```bash
# Edit the file locally, then rebuild container
docker-compose up -d --build stock-api
```

### Analysis Style

Edit `analysis_prompt.txt` to customize your AI's analysis approach (used by host scripts).

## Daily Automation with Cron

### Option 1: Cron with API (Recommended)

The Stock API server runs 24/7 in Docker, so you just need to trigger it:

```bash
# Edit crontab
crontab -e

# Add this line - runs at 9 AM daily
0 9 * * * curl -X POST http://localhost:13052/api/news/get -H "Content-Type: application/json" -d '{"max_items": 100, "top_k": 50}' >> /path/to/auto-news/cron.log 2>&1

# Optional: Also trigger Claude analysis at 9:05 AM (for openclaw integration)
# Requires Claude CLI authentication: docker exec -it idx-stock-api su appuser -c "claude /login"
5 9 * * * curl http://localhost:13052/api/news/analyze >> /path/to/auto-news/cron_analysis.log 2>&1
```

**Perfect for openclaw integration:** Set up cron to automatically generate daily market reports, then use openclaw to send them to Slack/Discord channels!

### Option 2: Cron with Host Scripts

```bash
# Edit crontab
crontab -e

# Add this line:
0 9 * * * cd /path/to/auto-news && bash run_daily_analysis.sh >> cron.log 2>&1
```

### Keep Services Running

Docker containers automatically restart (configured with `restart: unless-stopped`):

```bash
# Verify all containers are running
docker ps | grep -E "idx-stock-api|idx-report-server|milvus|etcd|minio"

# Check services health
curl http://localhost:13052/    # Stock API
curl http://localhost:3131/     # Report Server
```

All services including the report server run 24/7 and restart automatically on system reboot!

## Troubleshooting

### Docker: Containers not starting

```bash
# Check if tunnel network exists
docker network ls | grep tunnel

# Create if missing
docker network create tunnel

# Start all services
docker-compose up -d

# Check logs if any container fails
docker-compose logs stock-api
docker-compose logs milvus-standalone
```

### MCP: Server not connecting to AI client

1. **Verify Docker container is running:**
   ```bash
   docker ps | grep idx-stock-api
   ```

2. **Test MCP server manually:**
   ```bash
   docker exec -i idx-stock-api python3 /app/mcp_server.py
   # Should start without errors
   ```

3. **Check MCP config syntax:**
   ```json
   {
     "mcpServers": {
       "stock-news": {
         "type": "stdio",
         "command": "docker",
         "args": ["exec", "-i", "idx-stock-api", "python3", "/app/mcp_server.py"]
       }
     }
   }
   ```

4. **Restart your MCP client** (Claude Desktop/Code or other)

### API: Cannot connect to http://localhost:13052

```bash
# Check if container is running
docker ps | grep idx-stock-api

# Check container logs
docker logs idx-stock-api

# Restart if needed
docker-compose restart stock-api

# Check health endpoint
curl http://localhost:13052/
```

### API: Milvus connection errors

```bash
# Verify Milvus is running
docker ps | grep milvus-standalone

# Check Milvus logs
docker logs milvus-standalone

# Restart Milvus stack if needed
docker-compose restart milvus-standalone etcd minio

# Wait 30 seconds for Milvus to initialize
sleep 30

# Test connection from inside stock-api container
docker exec -it idx-stock-api python3 -c "from pymilvus import connections; connections.connect(host='milvus-standalone', port='19530'); print('Connected!')"
```

### API: "Stock data not available" or Yahoo Finance errors

Some Indonesian stocks may have different ticker formats:
- IDX format: `BBCA`
- Yahoo Finance format: `BBCA.JK` (automatically appended by the API)

If issues persist:
1. Verify stock symbol is correct (check IDX website)
2. Try a different time period (some stocks have limited historical data)
3. Check internet connectivity from container:
   ```bash
   docker exec -it idx-stock-api curl -I https://finance.yahoo.com
   ```

### Port conflicts

**Port 13052 (Stock API) already in use:**
```bash
# Find process using port
lsof -ti:13052

# Option 1: Kill the process
lsof -ti:13052 | xargs kill -9

# Option 2: Change port in docker-compose.yml
# ports: - "13053:13052"
```

**Port 19530 (Milvus) already in use:**
```bash
# Check what's using it
lsof -ti:19530

# Stop conflicting services, then restart
docker-compose up -d
```

### Data persistence issues

```bash
# Check volume mounts
docker inspect idx-stock-api | grep -A 5 Mounts

# Verify data directory permissions
docker exec -it idx-stock-api ls -la /app/data/

# Manually check generated files
ls -lh volumes/news_data/
```

### Rebuild after code changes

```bash
# Rebuild stock-api container
docker-compose up -d --build stock-api

# Or rebuild everything
docker-compose down
docker-compose up -d --build
```

### Report Server: "Report Not Found" error

```bash
# Check if daily_report.md exists
ls -la volumes/news_data/daily_report.md

# If missing, generate it via API:
curl http://localhost:13052/api/news/analyze

# Or run via host script:
bash run_daily_analysis.sh

# Report server will auto-refresh and show the report
# Visit: http://localhost:3131
```

### Report Server: Cannot connect to http://localhost:3131

```bash
# Check if report server container is running
docker ps | grep idx-report-server

# Check container logs
docker logs idx-report-server

# Restart if needed
docker-compose restart report-server

# Verify it's listening
curl http://localhost:3131/
```

### Report Server: Not showing latest report

The report server auto-refreshes every 5 minutes. To force immediate refresh:

```bash
# Option 1: Refresh browser (Ctrl+R or Cmd+R)
# Option 2: Click the "🔄 Refresh" button in the top-right
# Option 3: Restart container to clear any caching
docker-compose restart report-server
```

### Claude CLI: Authentication issues

**Problem: `/api/news/analyze` returns "Claude CLI not configured"**

```bash
# 1. Check if Claude CLI is installed in container
docker exec -it idx-stock-api which claude
# Should return: /usr/local/bin/claude

# 2. Check if credentials exist
docker exec -it idx-stock-api su appuser -c "ls -la /home/appuser/.claude"
# Should show session files

# 3. Login if not authenticated
docker exec -it idx-stock-api su appuser -c "claude /login"

# 4. Verify login worked
docker exec -it idx-stock-api su appuser -c "claude -p 'test'" --dangerously-skip-permissions
# Should return a response from Claude
```

**Problem: "Forbidden" error when calling /api/news/analyze**

This endpoint only accepts requests from localhost/Docker network by design (for openclaw integration):

```bash
# ✅ This works (from same machine):
curl http://localhost:13052/api/news/analyze

# ❌ This fails (from external IP):
curl http://your-server-ip:13052/api/news/analyze

# To allow external access, set CLAUDE_SECRET_KEY in .env:
# 1. Generate a secret key:
openssl rand -hex 32

# 2. Add to .env:
echo "CLAUDE_SECRET_KEY=your-generated-key" >> .env

# 3. Restart container:
docker-compose restart stock-api

# 4. Call with header:
curl http://your-server-ip:13052/api/news/analyze \
  -H "X-Secret-Key: your-generated-key"
```

**Problem: Claude CLI credentials not persisting**

```bash
# Check volume mount
docker inspect idx-stock-api | grep claude_config

# Ensure volumes/claude_config/ exists and has correct permissions
mkdir -p volumes/claude_config
chmod 755 volumes/claude_config

# Restart container and login again
docker-compose restart stock-api
docker exec -it idx-stock-api su appuser -c "claude /login"
```

## Dependencies

### Docker (Required)

All Python dependencies are installed inside the Docker container. You don't need to install anything locally unless you want to run scripts outside Docker.

**System Requirements:**
- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum (8GB recommended for Milvus)
- 10GB disk space

### Python Packages (Auto-installed in Container)

See `src/stock_api/requirements.txt` for the complete list.

**Key packages:**
- `fastapi`, `uvicorn` - REST API server
- `pymilvus` - Vector database client
- `sentence-transformers` - Multilingual embeddings (paraphrase-multilingual-mpnet-base-v2)
- `torch` - Deep learning backend
- `mcp` - Model Context Protocol SDK
- `requests`, `beautifulsoup4` - Web scraping
- `yfinance` - Stock market data from Yahoo Finance
- `pandas`, `numpy` - Data analysis
- `ta` - Technical analysis indicators (RSI, MACD, Bollinger Bands, etc.)
- `python-dotenv` - Environment variable management

### Manual Installation (Optional)

Only needed if you want to run scripts outside Docker:

```bash
pip install -r requirements.txt
```

## Example Output

The generated `daily_report.md` includes:
- Market overview & sentiment
- Most mentioned stocks
- Price movements & catalysts
- Top 3 actionable recommendations
- Individual article analysis

## Features

### ✅ Implemented Features

#### 1. Containerized Architecture
- **Unified Docker Compose stack** - All services run in containers
- **Persistent data volumes** - News data, database, and configurations preserved
- **Auto-restart** - Containers restart automatically on failure
- **Health checks** - Built-in monitoring for all services
- **Separation of concerns** - Stock API (internal) + Report Server (public web UI)
- **Security-first design** - Report server has read-only access to data volume

#### 2. News Pipeline
- **Multi-source scraping** - Aggregate news from Indonesian financial sites
- **Semantic search** - Milvus vector database with multilingual embeddings
- **Deduplication** - Link-based deduplication to avoid duplicate articles
- **Configurable filtering** - Filter by date range, article count, relevance
- **Background processing** - Async pipeline execution with status tracking

#### 3. Stock Analysis APIs
- **Real-time data** - Yahoo Finance integration for IDX stocks
- **Technical indicators**:
  - Moving averages (SMA 20/50, EMA 12/26)
  - RSI (Relative Strength Index)
  - MACD (Moving Average Convergence Divergence)
  - Bollinger Bands
  - Volume analysis (OBV, ADL, VPT, MFI)
  - Average True Range (ATR)
- **Bandarmology analysis** - Smart money flow detection:
  - Accumulation/Distribution phases (Wyckoff-style)
  - Volume pattern recognition
  - Price structure analysis
  - Breakout triggers
  - Risk management levels (stop loss, take profit)
- **Fundamental data** - P/E, P/B, ROE, debt ratios, dividend yield, etc.
- **Mandiri Sekuritas-style reports** - Comprehensive analysis reports

#### 4. Trading Strategy Screening
- **PREOPEN setups** - Analyze overnight, execute at market open (08:45-08:58 WIB)
- **BPJS (Beli Pagi Jual Sore)** - Buy morning, sell afternoon same-day trades
- **BSJP (Beli Sore Jual Pagi)** - Buy afternoon, sell next morning
- **Day trade screening** - Mandiri-style intraday opportunities
- **Customizable filters** - Min score, volume, bandarmology toggle

#### 5. Market Context
- **Global sentiment** - S&P500, Nikkei, commodity impacts on IDX
- **Trading time context** - WIB time, current session, recommended strategies
- **Stock lists** - LQ45, IDX30 constituents

#### 6. MCP Integration
- **Docker-based MCP server** - Runs inside container for data volume sharing
- **5 MCP tools** - Pipeline status, async/sync execution, file checks, report reading
- **Universal compatibility** - Works with Claude Desktop, Claude Code, and other MCP clients

#### 7. REST API & Web UI
- **Comprehensive FastAPI server** - All features accessible via HTTP (internal port 13052)
- **Public web UI** - Report server on port 3131 (safe to expose publicly)
- **Interactive documentation** - Swagger UI at `/docs`
- **Security options** - Optional secret key authentication for sensitive endpoints
- **CORS enabled** - Ready for web dashboard integration
- **Read-only report access** - Web server has no write permissions

**Quick API Examples:**
```bash
# Get technical analysis
curl -X POST http://localhost:13052/api/stock/technicals \
  -d '{"symbol": "BBCA", "period": "6mo"}'

# Screen for day trades
curl -X POST http://localhost:13052/api/screen/day-trade \
  -d '{"stock_index": "LQ45", "limit": 10}'

# Run news pipeline
curl -X POST http://localhost:13052/api/news/get \
  -d '{"max_items": 100, "top_k": 50}'
```

## Future Enhancements

### Planned Features

#### High Priority

- **Unified Analysis Endpoint** ⏳
  - Cross-reference fundamental news with technical signals
  - Identify stocks where both analyses align (strong buy/sell signals)
  - Flag divergences (e.g., positive news but bearish technicals)
  - Generate confidence scores based on multi-factor agreement
  - Example: `POST /api/stock/unified_analysis` → Combined recommendation

- **MCP Stock Analysis Tools** ⏳
  - Expose stock analysis via MCP (currently only news pipeline is available)
  - `get_stock_price` - Query prices from AI assistants
  - `get_technical_analysis` - Get indicators via AI
  - `get_bandarmology` - Get smart money flow via AI
  - `screen_stocks` - Run screening strategies via AI

- **Sentiment Analysis** ⏳
  - NLP sentiment scoring for news articles
  - Aggregate sentiment by stock ticker
  - Correlation with price movements

#### Medium Priority

- **Alert System**
  - WhatsApp/Telegram notifications for critical market events
  - Configurable thresholds (price changes, volume spikes, news mentions)
  - Daily summary reports via messaging apps

- **Portfolio Tracking**
  - Monitor your holdings against news/technical signals
  - Performance analytics and P&L tracking
  - Alerts when your stocks appear in news or screening results

- **Real-time Updates**
  - WebSocket integration for live market data
  - Push notifications for price movements
  - Live screening results as market conditions change

#### Low Priority

- **Multi-language Support**
  - Scrape English financial news sources (Bloomberg, Reuters)
  - Cross-reference Indonesian and global news

- **Backtesting Framework**
  - Test strategy performance against historical data
  - Evaluate screening criteria effectiveness
  - Risk/reward metrics and sharpe ratios

- **Advanced Deduplication**
  - Content similarity detection (beyond link-based)
  - Clustering of related news stories
  - Topic modeling for better organization

- **Web Dashboard**
  - Interactive UI for exploring data
  - Charting and visualization
  - Custom screening builder

**Contributions welcome!** Feel free to implement any of these features. Open an issue to discuss before starting work on major features.

## Migration Guide

### Upgrading from Previous Versions

If you're upgrading from an older version of auto-news, follow these steps:

#### 1. Stop Old Services

```bash
# If you had rag/ directory with docker-compose
cd rag
docker-compose down
cd ..

# Stop any running unified_api_server.py
pkill -f unified_api_server.py
```

#### 2. Update Configuration

**MCP Config Update:**
Old config (no longer works):
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

New config (Docker-based):
```json
{
  "mcpServers": {
    "stock-news": {
      "type": "stdio",
      "command": "docker",
      "args": ["exec", "-i", "idx-stock-api", "python3", "/app/mcp_server.py"]
    }
  }
}
```

**API Port Change:**
- Old: `http://localhost:13051`
- New: `http://localhost:13052`

Update any scripts or applications using the old port.

#### 3. Create Docker Network

```bash
docker network create tunnel
```

#### 4. Start New Stack

```bash
# From project root
docker-compose up -d

# Verify all services running (including new report-server)
docker ps
# Should see: etcd, minio, milvus-standalone, attu, idx-stock-api, idx-report-server
```

#### 5. Verify Migration

```bash
# Test Stock API
curl http://localhost:13052/

# Test Report Server (new!)
curl http://localhost:3131/
open http://localhost:3131

# Test MCP (restart your MCP client first)
# Then ask: "Check news pipeline status"
```

### Breaking Changes

- **MCP server location**: Moved from `src/mcp_server.py` to `src/stock_api/mcp_server.py`
- **API port**: Changed from 13051 to 13052
- **Report server**: Now runs in Docker container (port 3131), no need to run `serve_report.py` manually
- **Docker architecture**: `rag/docker-compose.yml` merged into root `docker-compose.yml`
- **File paths**: Pipeline scripts moved from root to `src/helper/`
- **MCP tools**: Changed from 3 tools to 5 tools (added status checking and file management)
- **Data location**: Now in `volumes/news_data/` instead of project root

### New Features in This Version

- **Report Server Container**: Dedicated lightweight container for public web UI
- **Read-only data access**: Report server mounts news_data volume as read-only
- **Security improvements**: Stock API can stay internal, only report server exposed publicly
- **Auto-restart**: Both API and report server restart automatically
- **Health checks**: Monitoring for all services

### What's Preserved

- All your existing data files (news.txt, daily_report.md) can be copied to `volumes/news_data/`
- Milvus collections and embeddings are preserved in `volumes/milvus/`
- Analysis prompts and scripts still work the same way

## Disclaimer

**Investment Risk:** This tool is for educational and informational purposes only. Always conduct your own research before making investment decisions.

**Web Scraping:** This tool scrapes publicly available news for personal use. Please:
- Respect the terms of service of scraped websites
- Use responsibly and avoid excessive server load
- Not use for commercial redistribution of scraped content
- Check `robots.txt` policies of target websites

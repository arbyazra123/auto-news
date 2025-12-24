# Auto-News - Indonesian Stock Market Analysis with Semantic Search (MCP Support)

Automated Indonesian stock market news analysis using **Milvus Vector Search + AI Assistants via Model Context Protocol (MCP)**.

Connect any MCP-compatible AI assistant (Claude, or other LLMs) and ask: *"Show me the fundamental news today"* to get instant market insights!

## Table of Contents

- [Complete Workflow](#complete-workflow)
- [Quick Start](#quick-start)
  - [Installation](#installation)
  - [Option 1: Use with MCP-Compatible AI Assistants](#option-1-use-with-mcp-compatible-ai-assistants-recommended)
  - [Option 2: Manual CLI Usage](#option-2-manual-cli-usage)
- [MCP Integration Details](#mcp-integration-details)
- [Files Overview](#files-overview)
- [Manual Step-by-Step Usage](#manual-step-by-step-usage)
- [Web Server Features](#web-server-features)
- [Configuration](#configuration)
- [Daily Automation with Cron](#daily-automation-with-cron)
- [Troubleshooting](#troubleshooting)
- [Dependencies](#dependencies)
- [Example Output](#example-output)
- [Future Enhancements](#future-enhancements)
- [Disclaimer](#disclaimer)
- [Contributing](#contributing)

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

### Useful Links
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

## Files Overview

### Core Scripts
- **`src/mcp_server.py`** - MCP server (connects AI assistants to pipeline)
- **`scraper.py`** - Scrapes financial news (unlimited articles)
- **`rag_indexer.py`** - Embeds & stores articles in Milvus
- **`rag_query.py`** - Semantic search for relevant articles
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

## Example Output

The generated `daily_report.md` includes:
- Market overview & sentiment
- Most mentioned stocks
- Price movements & catalysts
- Top 3 actionable recommendations
- Individual article analysis

## Future Enhancements

This project has significant potential for expansion. Here are planned enhancements:

### Technical Analysis Integration

**Combine fundamental + technical analysis for better trading decisions:**

- **Data Source**: Fetch real-time stock data from Yahoo Finance API
- **Technical Indicators**: Calculate using Python (pandas-ta, ta-lib):
  - Moving averages (SMA, EMA)
  - RSI (Relative Strength Index)
  - MACD (Moving Average Convergence Divergence)
  - Bollinger Bands
  - Volume analysis
  - Support/Resistance levels

- **Analysis Matching**:
  - Cross-reference fundamental news with technical signals
  - Identify stocks where both analyses align (strong buy/sell signals)
  - Flag divergences (e.g., positive news but bearish technicals)
  - Generate confidence scores based on multi-factor agreement

- **Enhanced MCP Tool**: Add `get_stock_analysis` tool that combines:
  ```
  Fundamental (from news) + Technical (from Yahoo Finance) → Unified Recommendation
  ```

**Example Output:**
```
Stock: BBCA
Fundamental: Positive (strong earnings, dividend yield)
Technical: Bullish (RSI oversold, golden cross forming)
Verdict: STRONG BUY (both analyses align)
Confidence: 85%
```

### Other Potential Enhancements

- **Multi-language support**: Scrape English financial news sources
- **Sentiment analysis**: Add NLP sentiment scoring to news articles
- **Alert system**: WhatsApp/Telegram notifications for critical market events
- **Portfolio tracking**: Monitor your holdings against news/technical signals
- **Backtesting**: Test strategy performance against historical data
- **Real-time updates**: WebSocket integration for live market data

**Contributions welcome!** Feel free to implement any of these features.

## Disclaimer

**Investment Risk:** This tool is for educational and informational purposes only. Always conduct your own research before making investment decisions.

**Web Scraping:** This tool scrapes publicly available news for personal use. Please:
- Respect the terms of service of scraped websites
- Use responsibly and avoid excessive server load
- Not use for commercial redistribution of scraped content
- Check `robots.txt` policies of target websites

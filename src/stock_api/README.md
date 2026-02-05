# Indonesian Stock Analysis API - Docker Deployment

REST API for analyzing Indonesian stocks (IDX) with technical and bandarmology analysis.

## Quick Start

### Using Makefile (Easiest)

```bash
cd src/stock_api

# Build and run the container
make build
make run

# Or use docker-compose
make up

# View logs
make logs

# Restart the container
make restart

# Stop and clean up
make clean

# See all available commands
make help
```

**Note:** Make sure to run these commands from the `src/stock_api/` directory.

### Using Docker Compose (Recommended)

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

### Using Docker CLI

```bash
cd src/stock_api

# Build the image (note: context is parent directory to access helper modules)
docker build -t idx-stock-api -f Dockerfile ..

# Run the container
docker run -d \
  --name idx-stock-api \
  -p 13052:13052 \
  --restart unless-stopped \
  idx-stock-api

# View logs
docker logs -f idx-stock-api

# Stop the container
docker stop idx-stock-api
docker rm idx-stock-api
```

## Accessing the API

Once the container is running:

- **API Base URL:** http://localhost:13052
- **Interactive Docs:** http://localhost:13052/docs
- **ReDoc:** http://localhost:13052/redoc

## Available Endpoints

### Stock Analysis
- `POST /api/stock/price` - Get current stock price
- `POST /api/stock/history` - Get historical OHLCV data
- `POST /api/stock/technicals` - Get technical indicators (RSI, MACD, MAs, BBands)
- `POST /api/stock/bandarmology` - Get bandarmology analysis (smart money flow)
- `POST /api/stock/fundamentals` - Get fundamental data (P/E, P/B, etc.)
- `POST /api/stock/mandiri-report` - Get Mandiri Sekuritas-style report

### Trading Strategies
- `POST /api/screen/preopen` - Screen for pre-open setups
- `POST /api/screen/bpjs` - Screen for BPJS (Beli Pagi Jual Sore) setups
- `POST /api/screen/bsjp` - Screen for BSJP (Beli Sore Jual Pagi) setups
- `POST /api/screen/day-trade` - Screen for day trade opportunities

### Market Context
- `POST /api/market/global` - Check global markets sentiment
- `POST /api/market/time-context` - Get WIB time and trading session
- `POST /api/market/stock-list` - Get list of stocks by index (LQ45, IDX30)

## Example Usage

```bash
# Get stock price
curl -X POST http://localhost:13052/api/stock/price \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BBCA"}'

# Get bandarmology analysis
curl -X POST http://localhost:13052/api/stock/bandarmology \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BBRI", "period": "6mo"}'

# Screen for BPJS setups
curl -X POST http://localhost:13052/api/screen/bpjs \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "min_score": 65}'
```

## Environment Variables

The API uses the following default configuration:

- **Host:** 127.0.0.1 (inside container, exposed via port mapping)
- **Port:** 13052

## Health Check

The container includes a health check that runs every 30 seconds:

```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' idx-stock-api
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs

# Or for Docker CLI
docker logs idx-stock-api
```

### Port already in use

```bash
# Check what's using port 13052
lsof -i :13052

# Or use a different port in docker-compose.yml
ports:
  - "8052:13052"  # Map host port 8052 to container port 13052
```

### Rebuild after code changes

```bash
cd src/stock_api

# Docker Compose
docker-compose up -d --build

# Docker CLI
docker build -t idx-stock-api -f Dockerfile .. --no-cache
docker stop idx-stock-api
docker rm idx-stock-api
docker run -d --name idx-stock-api -p 13052:13052 idx-stock-api
```

## Development

To run in development mode with code hot-reload:

```bash
# Install dependencies locally
pip install -r requirements.txt

# Run directly
python stock_api_server.py
```

## Project Structure

```
src/stock_api/
├── Dockerfile              # Docker image configuration
├── docker-compose.yml      # Docker Compose setup
├── requirements.txt        # Python dependencies
├── stock_api_server.py     # Main API server
├── Makefile               # Convenience commands
└── README.md              # This file

Includes:
└── ../helper/             # Shared helper modules (news pipeline, etc.)
    ├── scraper.py
    ├── rag_indexer.py
    ├── rag_query.py
    ├── news_pipeline.py
    └── serve_report.py
```

## Resource Requirements

- **Memory:** ~1.5GB (includes ML models for news pipeline)
- **CPU:** 1-2 cores (varies with API load and ML inference)
- **Disk:** ~2GB for image (includes PyTorch and transformers)

## License

See main project license.

#!/usr/bin/env python3
"""
MCP Server for Auto-News
Provides Claude with access to Indonesian stock market news
"""

import asyncio
import subprocess
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


def log(message: str):
    """Log to stderr to avoid interfering with JSON-RPC on stdout."""
    print(message, file=sys.stderr, flush=True)

# Project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# Use the same Python interpreter that's running this script
# This ensures we use the correct conda environment
PYTHON_EXECUTABLE = sys.executable

app = Server("auto-news-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for Claude to use."""
    return [
        Tool(
            name="get_news",
            description=(
                "Retrieve today's fundamental Indonesian stock market news. "
                "This will run the full news pipeline: scraping articles, indexing them "
                "in the vector database, and querying the most relevant articles using "
                "semantic search. Returns condensed, relevant news articles ready for analysis."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "max_items": {
                        "type": "number",
                        "description": "Maximum total number of articles to scrape (default: 50)",
                        "default": 100,
                    },
                    "query": {
                        "type": "string",
                        "description": (
                            "Semantic search query to find relevant articles "
                            "(default: 'today's indonesia stock market movements, price changes, trading analysis, and financial news')"
                        ),
                        "default": "today's indonesia stock market movements, price changes, trading analysis, and financial news",
                    },
                    "top_k": {
                        "type": "number",
                        "description": "Number of top relevant articles to retrieve (default: 50)",
                        "default": 50,
                    },
                    "days_back": {
                        "type": "number",
                        "description": "Get articles from last N days (default: 1 for today only)",
                        "default": 1,
                    },
                    "max_chars": {
                        "type": "number",
                        "description": "Maximum characters per article content (default: 2000)",
                        "default": 2000,
                    },
                },
            },
        ),
        Tool(
            name="read_condensed_news",
            description=(
                "Read the latest condensed news file (news_condensed.txt) that was generated "
                "by the news pipeline. Use this if the news has already been fetched and you "
                "just want to read the results without running the full pipeline again."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="check_docker_status",
            description=(
                "Check if the required Docker containers (Milvus, etcd, minio) are running. "
                "This is useful for troubleshooting if the news pipeline fails."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


async def check_docker_status_internal() -> dict:
    """Check if required Docker containers are running."""
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--format",
                "{{.Names}}",
                "--filter",
                "name=milvus-standalone",
                "--filter",
                "name=etcd",
                "--filter",
                "name=minio",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        running_containers = [name for name in result.stdout.strip().split("\n") if name]
        required_containers = ["milvus-standalone", "etcd", "minio"]

        missing_containers = [
            name for name in required_containers if name not in running_containers
        ]

        if not missing_containers:
            return {
                "all_running": True,
                "message": "All required Docker containers are running.",
                "running_containers": running_containers,
            }
        else:
            return {
                "all_running": False,
                "message": f"Missing containers: {', '.join(missing_containers)}",
                "running_containers": running_containers,
                "missing_containers": missing_containers,
            }
    except Exception as e:
        return {
            "all_running": False,
            "message": f"Error checking Docker status: {str(e)}",
            "running_containers": [],
            "error": str(e),
        }


async def read_condensed_news_internal() -> str:
    """Read the condensed news file."""
    news_path = PROJECT_ROOT / "news_condensed.txt"

    if not news_path.exists():
        raise FileNotFoundError(
            "news_condensed.txt not found. Please run get_news first to generate the news file."
        )

    return news_path.read_text(encoding="utf-8")


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from Claude."""
    try:
        if name == "get_news":
            return await get_news(arguments)
        elif name == "read_condensed_news":
            return await read_condensed_news()
        elif name == "check_docker_status":
            return await check_docker_status()
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def get_news(args: dict) -> list[TextContent]:
    """Run the news pipeline and return condensed news."""
    max_items = args.get("max_items", 100)
    query = args.get(
        "query",
        "today's indonesia stock market movements, price changes, trading analysis, and financial news",
    )
    top_k = args.get("top_k", 50)
    days_back = args.get("days_back", 1)
    max_chars = args.get("max_chars", 2500)

    # First check if Docker containers are running
    docker_status = await check_docker_status_internal()
    if not docker_status["all_running"]:
        message = (
            f"Cannot run news pipeline: Required Docker containers are not running.\n\n"
            f"{docker_status['message']}\n\n"
            f"Please start the Docker containers:\n"
            f"  cd {PROJECT_ROOT}/rag\n"
            f"  docker-compose up -d"
        )
        return [TextContent(type="text", text=message)]

    try:
        # Remove existing news files to ensure fresh data
        news_txt_path = PROJECT_ROOT / "news.txt"
        news_condensed_path = PROJECT_ROOT / "news_condensed.txt"

        if news_txt_path.exists():
            news_txt_path.unlink()
            log("[MCP] Removed existing news.txt")

        if news_condensed_path.exists():
            news_condensed_path.unlink()
            log("[MCP] Removed existing news_condensed.txt")

        # Modify the rag_query.py call in the pipeline to use custom parameters
        # We'll run the steps manually with custom parameters
        log(f"[MCP] Running news pipeline with parameters:")
        log(f"[MCP]   max_items={max_items}, query='{query}'")
        log(f"[MCP]   top_k={top_k}, days_back={days_back}, max_chars={max_chars}")

        # Step 1: Scrape news
        log(f"[MCP] Step 1: Scraping up to {max_items} news articles...")
        result = subprocess.run(
            [PYTHON_EXECUTABLE, "src/helper/scraper.py", "--max_items", str(max_items)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
        )
        if result.returncode != 0:
            return [
                TextContent(
                    type="text",
                    text=f"Error scraping news:\n{result.stderr}",
                )
            ]

        # Step 2: Index articles
        log("[MCP] Step 2: Indexing articles into Milvus...")
        result = subprocess.run(
            [PYTHON_EXECUTABLE, "src/helper/rag_indexer.py"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            return [
                TextContent(
                    type="text",
                    text=f"Error indexing articles:\n{result.stderr}",
                )
            ]

        # Step 3: Query relevant articles with custom parameters
        log("[MCP] Step 3: Querying relevant articles...")
        result = subprocess.run(
            [
                PYTHON_EXECUTABLE,
                "src/helper/rag_query.py",
                "--query",
                query,
                "--top_k",
                str(top_k),
                "--days_back",
                str(days_back),
                "--max_chars",
                str(max_chars),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            return [
                TextContent(
                    type="text",
                    text=f"Error querying articles:\n{result.stderr}",
                )
            ]

        # Read the condensed news file
        news_content = await read_condensed_news_internal()

        pipeline_logs = (
            f"Successfully retrieved news!\n\n"
            f"Pipeline completed with parameters:\n"
            f"  Scraped Articles: {max_items}\n"
            f"  Search Query: {query}\n"
            f"  Top K Retrieved: {top_k}\n"
            f"  Days Back: {days_back}\n"
            f"  Max Chars: {max_chars}\n\n"
            f"{'='*60}\n\n"
            f"{news_content}"
        )

        return [TextContent(type="text", text=pipeline_logs)]

    except subprocess.TimeoutExpired:
        return [
            TextContent(
                type="text",
                text="Error: Pipeline execution timed out (exceeded 5 minutes)",
            )
        ]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=f"Failed to run news pipeline: {str(e)}",
            )
        ]


async def read_condensed_news() -> list[TextContent]:
    """Read the condensed news file."""
    try:
        content = await read_condensed_news_internal()
        return [TextContent(type="text", text=content)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error reading condensed news: {str(e)}")]


async def check_docker_status() -> list[TextContent]:
    """Check Docker container status."""
    status = await check_docker_status_internal()

    message = "Docker Status Check:\n\n"
    message += "Required containers: milvus-standalone, etcd, minio\n"
    message += f"Running containers: {', '.join(status['running_containers']) if status['running_containers'] else 'none'}\n\n"

    if status["all_running"]:
        message += "✓ All required containers are running!"
    else:
        message += f"✗ Missing containers: {', '.join(status.get('missing_containers', ['unknown']))}\n\n"
        message += "To start the containers:\n"
        message += f"  cd {PROJECT_ROOT}/rag\n"
        message += "  docker-compose up -d"

    return [TextContent(type="text", text=message)]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        log("[MCP] Auto-News MCP server running on stdio")
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

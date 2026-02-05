#!/usr/bin/env python3
"""
News Pipeline: End-to-end pipeline to scrape, index, and query news articles
Runs: scraper.py → rag_indexer.py → rag_query.py
Output: news_condensed.txt
"""
import subprocess
import sys
import argparse
from datetime import datetime
from pathlib import Path

def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)

def run_command(cmd, description):
    """Run a shell command and handle errors"""
    log(f"Starting: {description}")
    log(f"Running: {' '.join(cmd)}")

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=False,
            text=True
        )
        log(f"✓ Completed: {description}")
        return True
    except subprocess.CalledProcessError as e:
        log(f"✗ Failed: {description}")
        log(f"Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Run complete news pipeline: scrape → index → query",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with defaults
  python news_pipeline.py

  # Custom parameters
  python news_pipeline.py --max_items 50 --top_k 30 --days_back 1 --max_chars 1500

  # Get very recent news (last day)
  python news_pipeline.py --max_items 100 --days_back 1

  # Custom search query
  python news_pipeline.py --query "banking sector and financial technology news"
        """
    )

    # Scraper parameters
    parser.add_argument("--max_items", type=int, default=100,
                        help="Max articles to scrape (default: 100)")

    # RAG query parameters
    parser.add_argument("--query", type=str,
                        default="today's indonesia stock market movements, price changes, trading analysis, and financial news",
                        help="Search query for semantic search")
    parser.add_argument("--top_k", type=int, default=50,
                        help="Number of top relevant articles to retrieve (default: 50)")
    parser.add_argument("--days_back", type=int, default=None,
                        help="Get articles from last N days (default: None = all articles)")
    parser.add_argument("--max_chars", type=int, default=2000,
                        help="Max characters per article in output (default: 2000)")

    # Output
    parser.add_argument("--output", type=str, default="news_condensed.txt",
                        help="Final output file (default: news_condensed.txt)")

    # Optional: skip steps
    parser.add_argument("--skip_scrape", action="store_true",
                        help="Skip scraping step (use existing news.txt)")
    parser.add_argument("--skip_index", action="store_true",
                        help="Skip indexing step (use existing Milvus data)")

    args = parser.parse_args()

    # Get script directory
    script_dir = Path(__file__).parent

    log("="*60)
    log("NEWS PIPELINE STARTING")
    log("="*60)
    log(f"Pipeline configuration:")
    log(f"  - Scraper max_items: {args.max_items}")
    log(f"  - Query query: {args.query}")
    log(f"  - Query top_k: {args.top_k}")
    log(f"  - Query days_back: {args.days_back if args.days_back else 'all'}")
    log(f"  - Query max_chars: {args.max_chars}")
    log(f"  - Output file: {args.output}")
    log("="*60)

    # Step 1: Scrape news
    if not args.skip_scrape:
        scraper_cmd = [
            sys.executable,
            str(script_dir / "scraper.py"),
            "--max_items", str(args.max_items),
            "--output", "news.txt"
        ]

        if not run_command(scraper_cmd, "Step 1/3: Scraping news"):
            log("Pipeline failed at scraping step")
            return 1
    else:
        log("Step 1/3: Skipping scrape (using existing news.txt)")

    # Step 2: Index articles to Milvus
    if not args.skip_index:
        indexer_cmd = [
            sys.executable,
            str(script_dir / "rag_indexer.py")
        ]

        if not run_command(indexer_cmd, "Step 2/3: Indexing to Milvus"):
            log("Pipeline failed at indexing step")
            return 1
    else:
        log("Step 2/3: Skipping index (using existing Milvus data)")

    # Step 3: Query and export condensed news
    query_cmd = [
        sys.executable,
        str(script_dir / "rag_query.py"),
        "--query", args.query,
        "--top_k", str(args.top_k),
        "--max_chars", str(args.max_chars),
        "--output", args.output
    ]

    # Add days_back if specified
    if args.days_back is not None:
        query_cmd.extend(["--days_back", str(args.days_back)])

    if not run_command(query_cmd, "Step 3/3: Querying and exporting"):
        log("Pipeline failed at query step")
        return 1

    # Success!
    log("="*60)
    log("PIPELINE COMPLETED SUCCESSFULLY!")
    log(f"Output file: {args.output}")
    log("="*60)

    return 0

if __name__ == "__main__":
    sys.exit(main())

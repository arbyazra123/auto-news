#!/usr/bin/env python3
"""
RAG Query: Semantic search to retrieve most relevant articles
Query Milvus and return top N articles for analysis
"""
from datetime import datetime, timedelta
from pymilvus import connections, Collection
from sentence_transformers import SentenceTransformer

def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)

class NewsQuerier:
    def __init__(self, host="localhost", port="19530", collection_name="news_articles"):
        self.collection_name = collection_name
        self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

        log(f"Connecting to Milvus at {host}:{port}")
        connections.connect(alias="default", host=host, port=port)

        # Load collection
        self.collection = Collection(self.collection_name)
        self.collection.load()

        log(f"Loaded collection '{self.collection_name}' with {self.collection.num_entities} articles")

    def search(self, query, top_k=50, days_back=None, start_date=None, end_date=None):
        """
        Semantic search for relevant articles with flexible timestamp filtering

        Args:
            query: Search query (e.g., "today's market movements and stock analysis")
            top_k: Number of top relevant articles to return
            days_back: Get articles from last N days (e.g., 2 for last 2 days)
                       If set, overrides start_date/end_date
            start_date: Manual start date filter (format: "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS")
            end_date: Manual end date filter (format: "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS")

        Returns:
            List of articles with title, source, link, content, timestamp
        """
        log(f"Searching for: '{query}' (top {top_k} results)")

        # If days_back is set, calculate automatic date range
        if days_back is not None:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            log(f"Auto-filtering: last {days_back} days ({start_date} to {end_date})")

        # Build timestamp filter expression if dates provided
        filter_expr = None
        if start_date or end_date:
            conditions = []
            if start_date:
                # Ensure we have full timestamp format
                if len(start_date) == 10:  # Just date, add time
                    start_date = f"{start_date} 00:00:00"
                conditions.append(f'timestamp >= "{start_date}"')
                log(f"Filtering articles from: {start_date}")

            if end_date:
                # Ensure we have full timestamp format
                if len(end_date) == 10:  # Just date, add time
                    end_date = f"{end_date} 23:59:59"
                conditions.append(f'timestamp <= "{end_date}"')
                log(f"Filtering articles until: {end_date}")

            filter_expr = " and ".join(conditions)
            log(f"Filter expression: {filter_expr}")

        # Embed the query
        query_embedding = self.embedding_model.encode([query])[0].tolist()

        # Search parameters
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

        # Perform vector search with optional timestamp filter
        results = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr,  # Add timestamp filter
            output_fields=["title", "source", "link", "content", "timestamp"]
        )

        # Extract articles
        articles = []
        for hits in results:
            for hit in hits:
                articles.append({
                    "title": hit.entity.get("title"),
                    "source": hit.entity.get("source"),
                    "link": hit.entity.get("link"),
                    "content": hit.entity.get("content"),
                    "timestamp": hit.entity.get("timestamp"),
                    "score": hit.distance  # L2 distance (lower = more similar)
                })

        log(f"Found {len(articles)} relevant articles")
        return articles

    def export_to_condensed(self, articles, output_file="news_condensed.txt", max_chars=2000):
        """
        Export retrieved articles to condensed format for Claude
        Similar to claude_preprocess.py but for RAG results
        """
        log(f"Exporting {len(articles)} articles to {output_file}")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# Financial News Articles - RAG Retrieved & Condensed\n\n")
            f.write(f"Total Articles: {len(articles)}\n")
            f.write(f"Retrieved: Most relevant articles via semantic search\n")
            f.write("="*60 + "\n\n")

            for i, article in enumerate(articles, 1):
                # Truncate content if needed
                content = article['content']
                if len(content) > max_chars:
                    content = content[:max_chars] + "..."

                f.write(f"## Article {i}\n")
                f.write(f"**Title:** {article['title']}\n")
                f.write(f"**Source:** {article['source']}\n")
                f.write(f"**Link:** {article['link']}\n")
                f.write(f"**Timestamp:** {article['timestamp']}\n")
                f.write(f"**Content:** {content}\n")
                f.write(f"**Relevance Score:** {article['score']:.4f}\n")
                f.write("\n" + "-"*60 + "\n\n")

        log(f"Condensed file created: {output_file}")

def main():
    """
    Default query: Get today's most important market news
    You can customize this query based on what you want to analyze
    """
    import argparse

    parser = argparse.ArgumentParser(description="Query RAG for relevant news articles")
    parser.add_argument("--query", type=str,
                        default="today's stock market movements, price changes, trading analysis, and financial news",
                        help="Search query for semantic search")
    parser.add_argument("--top_k", type=int, default=50,
                        help="Number of top articles to retrieve")
    parser.add_argument("--days_back", type=int, default=None,
                        help="Get articles from last N days (e.g., --days_back 2 for last 2 days)")
    parser.add_argument("--start_date", type=str, default=None,
                        help="Start date filter (format: YYYY-MM-DD)")
    parser.add_argument("--end_date", type=str, default=None,
                        help="End date filter (format: YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default="news_condensed.txt",
                        help="Output file path")
    parser.add_argument("--max_chars", type=int, default=2000,
                        help="Max characters per article content")

    args = parser.parse_args()

    log("Starting RAG query")

    # Query Milvus
    querier = NewsQuerier()
    articles = querier.search(
        query=args.query,
        top_k=args.top_k,
        days_back=args.days_back,
        start_date=args.start_date,
        end_date=args.end_date
    )

    # Export to condensed format
    if articles:
        querier.export_to_condensed(articles, output_file=args.output, max_chars=args.max_chars)
        log(f"Success! {len(articles)} relevant articles exported to {args.output}")
    else:
        log("No articles found in database")

if __name__ == "__main__":
    main()

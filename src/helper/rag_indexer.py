#!/usr/bin/env python3
"""
RAG Indexer: Embeds and stores articles in Milvus
Scrape unlimited articles, store everything with semantic search capability
"""
import os
import re
from datetime import datetime
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from sentence_transformers import SentenceTransformer

def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)

class NewsIndexer:
    def __init__(self, host=None, port=None, collection_name="news_articles"):
        # Use environment variables if provided, otherwise use defaults
        host = host or os.getenv("MILVUS_HOST", "localhost")
        port = port or os.getenv("MILVUS_PORT", "19530")
        self.collection_name = collection_name
        self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')  # Supports Indonesian
        self.dim = 384  # Embedding dimension for this model

        log(f"Connecting to Milvus at {host}:{port}")
        connections.connect(alias="default", host=host, port=port)

        self._setup_collection()

    def _setup_collection(self):
        """Create or load Milvus collection with proper schema"""

        # Drop existing collection if exists (for fresh start)
        # if utility.has_collection(self.collection_name):
        #     log(f"Collection '{self.collection_name}' exists, dropping it for fresh start")
        #     utility.drop_collection(self.collection_name)

        # Define schema
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="link", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),  # Full content
            FieldSchema(name="timestamp", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim)
        ]

        schema = CollectionSchema(fields=fields, description="Financial news articles with embeddings")

        log(f"Creating collection '{self.collection_name}'")
        collection = Collection(name=self.collection_name, schema=schema)

        # Create IVF_FLAT index for vector similarity search
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        log("Creating vector index")
        collection.create_index(field_name="embedding", index_params=index_params)

        log("Collection setup complete")

    def parse_articles(self, file_path="news.txt"):
        """Parse articles from news.txt"""
        log(f"Parsing articles from {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        articles = []
        for block in text.split("### Article Start"):
            if "### Article End" not in block:
                continue
            block = block.split("### Article End")[0].strip()

            title_match = re.search(r"Title:\s*(.*)", block)
            source_match = re.search(r"Source:\s*(.*)", block)
            content_match = re.search(r"Content:\s*(.*)", block, re.S)

            if not (title_match and content_match):
                continue

            content = content_match.group(1).strip()
            if len(content) == 0:
                continue

            articles.append({
                "title": title_match.group(1).strip(),
                "source": source_match.group(1).strip() if source_match else "",
                "content": content
            })

        log(f"Found {len(articles)} valid articles")
        return articles

    def embed_articles(self, articles):
        """Generate embeddings for articles"""
        log(f"Generating embeddings for {len(articles)} articles")

        # Combine title and content for richer embeddings
        texts = [f"{a['title']} {a['content'][:1000]}" for a in articles]  # Use first 1000 chars
        embeddings = self.embedding_model.encode(texts, show_progress_bar=True)

        return embeddings.tolist()

    def get_existing_links(self):
        """Query Milvus to get all existing article links"""
        collection = Collection(self.collection_name)
        collection.load()

        # Query all links from the collection
        try:
            results = collection.query(
                expr="id > 0",  # Get all records
                output_fields=["link"]
            )
            existing_links = {result["link"] for result in results}
            log(f"Found {len(existing_links)} existing articles in Milvus")
            return existing_links
        except Exception as e:
            log(f"Could not query existing links (collection may be empty): {e}")
            return set()

    def index_articles(self, articles):
        """Store articles with embeddings in Milvus"""
        if not articles:
            log("No articles to index")
            return

        log(f"Checking {len(articles)} articles for duplicates")

        # Get existing links to prevent duplication
        existing_links = self.get_existing_links()

        # Filter out articles with duplicate links
        new_articles = []
        duplicate_count = 0
        for article in articles:
            link = article.get("link", article["source"])
            if link not in existing_links:
                new_articles.append(article)
            else:
                duplicate_count += 1

        if duplicate_count > 0:
            log(f"Skipping {duplicate_count} duplicate articles")

        if not new_articles:
            log("No new articles to index (all are duplicates)")
            return

        log(f"Indexing {len(new_articles)} new articles into Milvus")

        # Generate embeddings
        embeddings = self.embed_articles(new_articles)

        # Prepare data for insertion
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entities = [
            [a["title"] for a in new_articles],
            [a["source"] for a in new_articles],
            [a.get("link", a["source"]) for a in new_articles],  # Use source as fallback
            [a["content"][:65535] for a in new_articles],  # Truncate to max length
            [timestamp] * len(new_articles),
            embeddings
        ]

        # Insert into collection
        collection = Collection(self.collection_name)
        collection.insert(entities)
        collection.flush()

        log(f"Successfully indexed {len(new_articles)} new articles")
        log(f"Total articles in collection: {collection.num_entities}")

    def index_from_file(self, file_path="news.txt"):
        """Full pipeline: parse → embed → store"""
        articles = self.parse_articles(file_path)
        if articles:
            self.index_articles(articles)
            return len(articles)
        return 0

def main():
    log("Starting RAG indexer")

    indexer = NewsIndexer()
    count = indexer.index_from_file("news.txt")

    log(f"Indexing complete! Stored {count} articles in Milvus")
    log("Articles are now searchable via semantic search")

if __name__ == "__main__":
    main()

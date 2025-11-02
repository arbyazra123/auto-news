#!/usr/bin/env python3
"""
Test RAG pipeline components
Validates Milvus connection, indexing, and querying
"""
import sys
from datetime import datetime

def log(message: str, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    symbol = {
        "INFO": "ℹ",
        "SUCCESS": "✓",
        "ERROR": "✗",
        "WARNING": "⚠"
    }.get(level, "•")
    print(f"[{timestamp}] {symbol} {message}")

def test_imports():
    """Test if all required packages are installed"""
    log("Testing imports...")

    try:
        import requests
        import bs4
        from pymilvus import connections, Collection, utility
        from sentence_transformers import SentenceTransformer
        import torch
        log("All required packages imported successfully", "SUCCESS")
        return True
    except ImportError as e:
        log(f"Import error: {e}", "ERROR")
        log("Run: pip install -r requirements.txt", "WARNING")
        return False

def test_milvus_connection():
    """Test connection to Milvus"""
    log("Testing Milvus connection...")

    try:
        from pymilvus import connections
        connections.connect(alias="test", host="localhost", port="19530")
        log("Connected to Milvus successfully", "SUCCESS")
        connections.disconnect("test")
        return True
    except Exception as e:
        log(f"Milvus connection failed: {e}", "ERROR")
        log("Make sure Milvus is running: cd rag && ./start_milvus.sh", "WARNING")
        return False

def test_embedding_model():
    """Test embedding model loading"""
    log("Testing embedding model...")

    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        test_text = "This is a test article about stock market"
        embedding = model.encode([test_text])
        log(f"Embedding model loaded (dim={len(embedding[0])})", "SUCCESS")
        return True
    except Exception as e:
        log(f"Embedding model failed: {e}", "ERROR")
        return False

def test_sample_workflow():
    """Test a minimal indexing and querying workflow"""
    log("Testing sample RAG workflow...")

    try:
        from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
        from sentence_transformers import SentenceTransformer

        # Connect
        connections.connect(alias="test", host="localhost", port="19530")

        # Create test collection
        test_collection_name = "test_rag_pipeline"

        if utility.has_collection(test_collection_name):
            utility.drop_collection(test_collection_name)

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384)
        ]
        schema = CollectionSchema(fields=fields, description="Test collection")
        collection = Collection(name=test_collection_name, schema=schema)

        # Index
        model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        test_texts = [
            "Bank Indonesia raises interest rates",
            "Stock market shows positive momentum",
            "Technology sector leads market gains"
        ]
        embeddings = model.encode(test_texts).tolist()

        collection.insert([test_texts, embeddings])
        collection.flush()

        # Create index
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 2}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()

        # Query
        query_text = "What's happening with the stock market?"
        query_embedding = model.encode([query_text])[0].tolist()

        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param={"metric_type": "L2", "params": {"nprobe": 2}},
            limit=2,
            output_fields=["text"]
        )

        # Cleanup
        utility.drop_collection(test_collection_name)
        connections.disconnect("test")

        log(f"Sample workflow successful! Found {len(results[0])} results", "SUCCESS")
        return True

    except Exception as e:
        log(f"Sample workflow failed: {e}", "ERROR")
        return False

def main():
    log("Starting RAG pipeline tests...")
    log("")

    results = []

    # Run tests
    results.append(("Import packages", test_imports()))
    results.append(("Milvus connection", test_milvus_connection()))
    results.append(("Embedding model", test_embedding_model()))
    results.append(("Sample workflow", test_sample_workflow()))

    # Summary
    log("")
    log("="*60)
    log("Test Results:")
    log("="*60)

    passed = 0
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        log(f"{symbol} {test_name}: {status}", "SUCCESS" if result else "ERROR")
        if result:
            passed += 1

    log("="*60)
    log(f"Total: {passed}/{len(results)} tests passed")

    if passed == len(results):
        log("")
        log("All tests passed! RAG pipeline is ready to use", "SUCCESS")
        log("")
        log("Next steps:")
        log("  1. Run: bash prepare_news.sh")
        log("  2. Then: bash run_daily_analysis.sh")
        return 0
    else:
        log("")
        log("Some tests failed. Please fix the issues above.", "ERROR")
        return 1

if __name__ == "__main__":
    sys.exit(main())

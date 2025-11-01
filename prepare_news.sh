#!/bin/bash
# Step 1 & 2: Scrape news and preprocess

echo "🔍 Step 1: Scraping news..."
python3 main.py

echo ""
echo "📝 Step 2: Preprocessing for Claude..."
python3 claude_preprocess.py

echo ""
echo "✅ News preparation complete!"

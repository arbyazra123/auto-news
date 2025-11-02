import re
import json
from datetime import datetime

max_chars = 2000

def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)

def parse_articles(file_path):
    """Parse articles from news.txt"""
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
        if len(content_match.group(1).strip()) == 0:
            continue

        title = title_match.group(1).strip()
        source = source_match.group(1).strip() if source_match else ""
        content = content_match.group(1).strip()

        articles.append({
            "title": title,
            "source": source,
            "content": content
        })
    return articles


def extract_key_content(content, max_chars=400):
    """
    Extract most relevant parts of article:
    - First paragraph (context)
    - Sentences with numbers/percentages (key data)
    - Last sentence (often contains conclusion)
    """
    # Get first paragraph
    paragraphs = content.split('\n\n')
    intro = paragraphs[0] if paragraphs else content[:200]
    
    # Find sentences with numbers or percentages (usually key data)
    numeric_pattern = r'[^.!?]*(?:\d+(?:\.\d+)?%|\$\d+|\d+(?:\.\d+)?\s*(?:billion|million|trillion))[^.!?]*[.!?]'
    numeric_sentences = re.findall(numeric_pattern, content, re.IGNORECASE)
    
    # Combine intro + key data
    result = intro
    if numeric_sentences:
        result += " KEY DATA: " + " ".join(numeric_sentences[:2])
    
    # Truncate to max length
    if len(result) > max_chars:
        result = result[:max_chars] + "..."
    
    return result


def create_condensed_file(articles, output_file="news_condensed.txt"):
    """Create a condensed version optimized for Claude Pro upload"""
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Financial News Articles - Condensed for Analysis\n\n")
        f.write(f"Total Articles: {len(articles)}\n")
        f.write("="*60 + "\n\n")
        
        for i, article in enumerate(articles, 1):
            # Extract key content only
            condensed_content = extract_key_content(article['content'], max_chars=max_chars)
            
            f.write(f"## Article {i}\n")
            f.write(f"**Title:** {article['title']}\n")
            f.write(f"**Source:** {article['source']}\n")
            f.write(f"**Content:** {condensed_content}\n")
            f.write("\n" + "-"*60 + "\n\n")
    
    log(f"Created condensed file: {output_file}")


def create_structured_prompt(articles, output_file="claude_pro_prompt.txt"):
    """Create a ready-to-paste prompt with condensed articles"""
    
    prompt = """Please analyze these financial news articles and provide:

1. **Individual Summaries** - For each article, provide a 2-3 sentence summary focusing on:
   - Key market movements and price changes
   - Main catalysts or reasons
   - Sentiment (Bullish/Bearish/Neutral)

2. **Overall Market Analysis** - In 3-4 sentences, describe:
   - Dominant themes across all articles
   - Overall market sentiment
   - Key sectors in focus

3. **Top 3 Actionable Recommendations** - Provide specific, actionable advice with brief rationale.

---

# ARTICLES TO ANALYZE:

"""
    
    for i, article in enumerate(articles, 1):
        condensed_content = extract_key_content(article['content'], max_chars=max_chars)
        prompt += f"\n**[Article {i}]**\n"
        prompt += f"Title: {article['title']}\n"
        prompt += f"Source: {article['source']}\n"
        prompt += f"{condensed_content}\n"
        prompt += "\n---\n"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(prompt)
    
    log(f"Created ready-to-paste prompt: {output_file}")


def main():
    
    # Parse original articles
    log("Parsing articles from news.txt...")
    articles = parse_articles("news.txt")
    log(f"Found {len(articles)} articles")
    
    if not articles:
        log("No articles found in news.txt!")
        return
    
    # Calculate size reduction
    original_size = sum(len(a['content']) for a in articles)
    condensed_size = sum(len(extract_key_content(a['content'], max_chars)) for a in articles)
    reduction = ((original_size - condensed_size) / original_size) * 100
    
    #print(f"📊 Size Analysis:")
    #print(f"   Original: {original_size:,} characters")
    #print(f"   Condensed: {condensed_size:,} characters")
    #print(f"   Reduction: {reduction:.1f}%\n")
    log(f"Size detail: Original ({original_size:,}, Condensed: ({condensed_size:,}), Reduction: ({reduction:.1f})")
    
    # Create outputs
    log("Creating files...")
    create_condensed_file(articles)
    create_structured_prompt(articles)
    
    log("Successfully created news_condensed.txt")
    #print("\n" + "="*60)
    #print("✅ READY TO USE WITH CLAUDE PRO!")
    #print("="*60)
    #print("\nOption A: Upload 'news_condensed.txt' to Claude Pro")
    #print("Option B: Copy-paste 'claude_pro_prompt.txt' directly")
    #print("\nBoth options will give you complete analysis in 1 message!")


if __name__ == "__main__":
    main()

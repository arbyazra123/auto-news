import json
import os
import re
from mlx_lm import load, generate

# Load Mistral model (4-bit quantized)
model, tokenizer = load("mlx-community/Qwen2.5-0.5B-Instruct-4bit")

# -----------------------
# 1. Parse the input text
# -----------------------

def parse_articles(file_path):
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


# ----------------------------
# 2. Summarize each article
# ----------------------------

def summarize_article(article):
    # return article['content'][0:10]
    prompt = f"""
    You are a financial analyst. Summarize the following market news in 3 sentences,
    focusing on the key movements, market context, and potential implications.

    Title: {article['title']}
    Source: {article['source']}
    Content:
    {article['content']}
    """

    summary = generate(model, tokenizer, prompt, max_tokens=256)
    return summary.strip()


# ----------------------------
# 3. Create overall summary
# ----------------------------

def summarize_overall(all_summaries):
    combined_text = "\n".join(all_summaries)

    prompt = f"""
    You are a financial strategist. Given these market summaries, write a concise overall
    market summary that highlights key trends, sectors, and macroeconomic patterns.

    Summaries:
    {combined_text}
    """

    return generate(model, tokenizer, prompt, max_tokens=512).strip()


# ----------------------------
# 4. Generate recommendations
# ----------------------------

def extract_recommendations(overall_summary):
    prompt = f"""
    Based on the following market overview, extract actionable investment recommendations.

    Format the output in JSON array form, for example:
    [
      {{"sector": "Technology", "sentiment": "Positive", "recommendation": "Buy growth tech stocks due to strong earnings"}},
      {{"sector": "Energy", "sentiment": "Negative", "recommendation": "Avoid oil as global supply increases"}}
    ]

    Market Overview:
    {overall_summary}
    """

    output = generate(model, tokenizer, prompt, max_tokens=512)
    return output.strip()


# ----------------------------
# 5. Main pipeline
# ----------------------------

def main():
    file_path = "news.txt"
    summaries_file = "summaries_cache.json"

    print("📄 Parsing articles...")
    articles = parse_articles(file_path)
    print(f"Found {len(articles)} articles.\n")

    # Load cached summaries if available
    summaries = []
    summarized_titles = set()

    if os.path.exists(summaries_file):
        with open(summaries_file, "r", encoding="utf-8") as f:
            summaries = json.load(f)
            summarized_titles = {s["title"] for s in summaries}
        print(f"🧠 Loaded {len(summaries)} cached summaries from {summaries_file}\n")

    # Summarize only new/unprocessed articles
    # for i, article in enumerate(articles, 1):
    #     if article["title"] in summarized_titles:
    #         print(f"⏩ Skipping cached article {i}/{len(articles)}: {article['title']}")
    #         continue

    #     print(f"🧠 Summarizing article {i}/{len(articles)}: {article['title']}")
    #     try:
    #         summary = summarize_article(article)
    #         summaries.append({
    #             "title": article["title"],
    #             "source": article["source"],
    #             "summary": summary
    #         })

    #         # Save after each article (auto checkpoint)
    #         with open(summaries_file, "w", encoding="utf-8") as f:
    #             json.dump(summaries, f, indent=2, ensure_ascii=False)

    #     except Exception as e:
    #         print(f"❌ Error summarizing {article['title']}: {e}")
    #         break

    print("\n✅ Saved all article summaries to summaries_cache.json")

    # Combine summaries
    all_summaries = [s["summary"] for s in summaries]

    print("\n🧩 Creating overall summary...")
    overall_summary = summarize_overall(all_summaries)
    print("\n=== MARKET SUMMARY ===\n")
    print(overall_summary)

    print("\n💡 Extracting recommendations...")
    recommendations = extract_recommendations(overall_summary)
    print("\n=== RECOMMENDATIONS ===\n")
    print(recommendations)


if __name__ == "__main__":
    main()

import json
import os
import re
from llama_cpp import Llama

# Load GGUF model using llama-cpp-python
# Download a GGUF model file first, e.g., from HuggingFace
# Example: Qwen2.5-0.5B-Instruct quantized GGUF
MODEL_PATH = "ShortGPT-Qwen2.5-4B.Q6_K.gguf"  # Update this path

# Initialize the model
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=9422,  # Context window
    # n_threads=4,  # Number of CPU threads
    n_gpu_layers=0,  # Set to -1 to use GPU, 0 for CPU only
    verbose=False
)

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
# 2. Helper function to generate text
# ----------------------------

def generate_text(prompt, max_tokens=256, temperature=0.7, stop=None):
    """Generate text using the GGUF model"""
    output = llm(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        stop=stop,
        echo=False
    )
    return output['choices'][0]['text'].strip()


# ----------------------------
# 3. Summarize each article
# ----------------------------

def summarize_article(article):
    prompt = f"""You are a financial analyst. Summarize the following market news in 3 sentences,
focusing on the key movements, market context, and potential implications.

Title: {article['title']}
Source: {article['source']}
Content:
{article['content']}

Summary:"""

    summary = generate_text(prompt, max_tokens=256, temperature=0.5)
    return summary.strip()


# ----------------------------
# 4. Create overall summary
# ----------------------------

def summarize_overall(all_summaries):
    combined_text = "\n".join(all_summaries)

    prompt = f"""You are a financial strategist. Given these market summaries, write a concise overall
market summary that highlights key trends, sectors, and macroeconomic patterns.

Summaries:
{combined_text}

Overall Summary:"""

    return generate_text(prompt, max_tokens=512, temperature=0.5)


# ----------------------------
# 5. Generate recommendations
# ----------------------------

def extract_recommendations(overall_summary):
    prompt = f"""Based on the following market overview, extract actionable investment recommendations.

Format the output in JSON array form, for example:
[
  {{"sector": "Technology", "sentiment": "Positive", "recommendation": "Buy growth tech stocks due to strong earnings"}},
  {{"sector": "Energy", "sentiment": "Negative", "recommendation": "Avoid oil as global supply increases"}}
]

Market Overview:
{overall_summary}

JSON Output:"""

    output = generate_text(prompt, max_tokens=512, temperature=0.3)
    return output.strip()


# ----------------------------
# 6. Main pipeline
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

    # print("\n✅ Saved all article summaries to summaries_cache.json")

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
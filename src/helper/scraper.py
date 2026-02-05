import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime, date

def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/118.0.0.0 Safari/537.36"
    )
}

def get_sites():
    return [
        {
            "url": "https://wartaekonomi.co.id/category-283/bursa",
            "item_tag": "div.articleListWrapper",
        },
        {
            "url": "https://market.bisnis.com/bursa-saham",
            "item_tag": "div.art--row",
        },
        {
            "url": "https://www.cnbcindonesia.com/tag/saham",
            "item_tag": "div.nhl-list",
        },
        {
            "url": "https://www.idxchannel.com/indeks",
            "item_tag": "div.bt-con",
        },
        {
            "url": "https://www.liputan6.com/saham",
            "item_tag": "article.articles--iridescent-list--item",
        },
        {
            "url": "https://insight.kontan.co.id/rubrik/171/Market",
            "item_tag": "div.card__item--horizon",
        },
    ]


def scrape_site(config, max_item=50):
    """
    Scrape one site based on config.
    Collects articles up to max_item limit.
    """
    results = []
    url = config["url"]

    while url and len(results) < max_item:
        log(f"Crawling {url}")

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            log(f"⚠️ Failed to fetch {url}: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(config["item_tag"])
        if not items:
            log(f"No items found on {url}")
            break

        for item in items:
            if len(results) >= max_item:
                break
            title_tag = item.find("a", href=True)
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            link = urljoin(url, title_tag["href"])

            # fetch detail content
            try:
                detail_resp = requests.get(link, headers=headers, timeout=30)
                detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                content = " ".join(p.get_text(" ", strip=True) for p in detail_soup.find_all("p"))

                if not title:
                    # Extract title from the URL slug
                    path = urlparse(link).path  # e.g. "/2025/11/02/stock-market-analysis-today.html"
                    slug = path.strip("/").split("/")[-1]  # e.g. "stock-market-analysis-today.html"
                    slug = slug.split(".")[0]  # remove ".html" if present
                    title = slug.replace("-", " ").replace("_", " ").title()

            except Exception as e:
                content = f"(could not fetch detail: {e})"

            results.append({
                "title": title,
                "link": link,
                "content": content
            })

        # Stop pagination since we control total via max_item
        url = None

    return results

def save_to_txt(articles, filename="news.txt"):
    with open(filename, "a", encoding="utf-8") as f:
        for art in articles:
            f.write("### Article Start\n")
            f.write(f"Title: {art.get('title','')}\n")
            f.write(f"Source: {art.get('link','')}\n")
            f.write("Content:\n")
            f.write(art.get("content", "") + "\n")
            f.write("### Article End\n\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Indonesian stock market news")
    parser.add_argument("--max_items", type=int, default=100,
                        help="Maximum total number of articles to scrape (default: 100)")
    parser.add_argument("--output", type=str, default="news.txt",
                        help="Output file path (default: news.txt)")

    args = parser.parse_args()

    # Calculate items per site
    sites = get_sites()
    items_per_site = max(1, args.max_items // len(sites))

    log(f"Scraping up to {args.max_items} total articles ({items_per_site} per site)")

    all_results = []
    for site in sites:
        if len(all_results) >= args.max_items:
            break
        remaining = args.max_items - len(all_results)
        max_for_site = min(items_per_site, remaining)
        all_results.extend(scrape_site(site, max_item=max_for_site))

    save_to_txt(all_results, filename=args.output)
    log(f"Collected {len(all_results)} articles -> {args.output}")

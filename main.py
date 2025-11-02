import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
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
            "time_tag": "time.text-muted",
            "pagination_tag": None,
        },
        {
            "url": "https://market.bisnis.com/bursa-saham",
            "item_tag": "div.art--row",
            "time_tag": "div.artDate",
            "pagination_tag": "a.btn.page-link.text-dark",
        },
        {
            "url": "https://www.cnbcindonesia.com/tag/saham",
            "item_tag": "div.nhl-list",
            "time_tag": None,
            "pagination_tag": None,
        },
        {
            "url": "https://www.idxchannel.com/market-news",
            "item_tag": "div.bt-con",
            "time_tag": None,
            "pagination_tag": None,
        },
    ]


def scrape_site(config, max_pages=3, max_item=15):
    """
    Scrape one site based on config.
    Only collects today's articles, follows pagination up to max_pages.
    """
    results = []
    url = config["url"]
    pages_crawled = 0

    while url and pages_crawled < max_pages:
        pages_crawled += 1
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
            log(f"❌ No items found on {url}")
            break

        # today_str = date.today().strftime("%Y-%m-%d")  # YYYY-MM-DD
        curr_item = 0
        for item in items:
            if curr_item >= max_item:
                break
            title_tag = item.find("a", href=True)
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            link = urljoin(url, title_tag["href"])

            # extract time
            # pub_time = None
            # if config["time_tag"]:
            #     time_tag = item.select_one(config["time_tag"])
            #     if time_tag:
            #         pub_time = time_tag.get_text(strip=True)

            # ✅ filter only today's news
            # if pub_time and today_str not in pub_time:
            #     continue

            # fetch detail content
            try:
                detail_resp = requests.get(link, headers=headers, timeout=15)
                detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                content = " ".join(p.get_text(" ", strip=True) for p in detail_soup.find_all("p"))
            except Exception as e:
                content = f"(could not fetch detail: {e})"

            results.append({
                "title": title,
                "link": link,
                # "time": pub_time,
                "content": content
            })
            curr_item += 1

        # find pagination (if any)
        if config["pagination_tag"]:
            next_page = soup.select_one(config["pagination_tag"])
            if next_page and next_page.get("href"):
                url = urljoin(url, next_page["href"])
            else:
                url = None
        else:
            url = None

    return results

def save_to_txt(articles, filename="news.txt"):
    with open(filename, "a", encoding="utf-8") as f:
        for art in articles:
            f.write("### Article Start\n")
            f.write(f"Title: {art.get('title','')}\n")
            # f.write(f"Date: {art.get('time','')}\n")
            f.write(f"Source: {art.get('link','')}\n")
            f.write("Content:\n")
            # save first 500 chars if content is too long
            # content = art.get("content", "")
            # if len(content) > 500:
            #     content = content[:500] + "..."
            # f.write(content.strip() + "\n")
            f.write(art.get("content", "") + "\n")
            f.write("### Article End\n\n")

            
if __name__ == "__main__":
    all_results = []
    for site in get_sites():
        all_results.extend(scrape_site(site, max_pages=2))
    save_to_txt(all_results)
    log(f"Collected {len(all_results)} news")

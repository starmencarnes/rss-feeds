import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime
from urllib.parse import urljoin
import feedparser
import logging
import pandas as pd

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Load feed definitions from Google Sheets CSV
CSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vTV_T00K1ge75QzOx1PKKjOtQ1HELAXRS02OuQsleQSMMHaVbj85XSSu-p0i2AV3OYHPL32E3HdGN15/"
    "pub?gid=1189172550&single=true&output=csv"
)

def load_feeds(csv_url):
    """Fetch and parse the Google Sheet CSV into a list of dicts."""
    logging.info(f"Fetching feed config from {csv_url}")
    df = pd.read_csv(csv_url)
    # Ensure columns: name,url,feed_url,category,locale,limit
    df = df.where(pd.notnull(df), None)  # convert NaN to None
    feeds = df.to_dict(orient="records")
    logging.info(f"Loaded {len(feeds)} feed definitions")
    return feeds

WEBSITES = load_feeds(CSV_URL)

# (rest of your helper functions remain unchanged)…

def extract_title(article):
    link_elem = article.find("a", attrs={"title": True})
    if link_elem and link_elem.get("title"):
        return link_elem["title"], link_elem.get("href", "#")
    h2_elem = article.find("h2")
    if h2_elem:
        a_tag = h2_elem.find("a")
        if a_tag:
            return a_tag.get_text(strip=True), a_tag.get("href", "#")
        return h2_elem.get_text(strip=True), "#"
    meta_title = article.find("meta", property="og:title")
    if meta_title and meta_title.get("content"):
        return meta_title["content"], "#"
    if article.name == "a" and article.get("title"):
        return article["title"], article.get("href", "#")
    return "No Title", "#"

def scrape_rss_feed(site):
    feed_url = site.get("feed_url")
    if not feed_url:
        return []
    logging.info(f"{site['name']}: Parsing RSS feed from {feed_url}")
    parsed = feedparser.parse(feed_url)
    articles = []
    limit = site.get("limit") or 10
    for entry in parsed.entries[:limit]:
        title = entry.get("title", "No Title")
        link = entry.get("link", "#")
        if getattr(entry, "published_parsed", None):
            pub = datetime(*entry.published_parsed[:6])
        else:
            try:
                pub = datetime.strptime(entry.get("published", ""), "%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pub = datetime.min
        articles.append({
            "title": title,
            "link": link,
            "site": site["name"],
            "category": site["category"],
            "locale": site.get("locale", "Unknown"),
            "date": pub
        })
    logging.info(f"{site['name']}: Parsed {len(articles)} items")
    return articles

def scrape_website(site):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(site["url"], headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch {site['name']}: {e}")
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    found = soup.find_all("article") or \
            soup.find_all("div", class_=lambda c: c and any(kw in c.lower() for kw in ["post","entry","story"])) or \
            soup.find_all("a", href=True)
    logging.info(f"{site['name']}: Found {len(found)} candidate elements")
    articles = []
    limit = site.get("limit") or 10
    for elm in found[:limit]:
        title, link = extract_title(elm)
        link = urljoin(site["url"], link)
        time_el = elm.find("time")
        raw_dt = time_el.get("datetime") if time_el and time_el.get("datetime") else "1970-01-01T00:00:00Z"
        try:
            pub = datetime.strptime(raw_dt, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pub = datetime.min
        articles.append({
            "title": title,
            "link": link,
            "site": site["name"],
            "category": site["category"],
            "locale": site.get("locale", "Unknown"),
            "date": pub
        })
    logging.info(f"{site['name']}: Scraped {len(articles)} items")
    return articles

# Build the unified feed
fg = FeedGenerator()
fg.title("Custom Multi‑Site RSS Feed")
fg.link(href="https://starmencarnes.github.io/rss-feeds/index.xml", rel="self")
fg.description("Automatically generated RSS feed for multiple websites.")

all_articles = []
for site in WEBSITES:
    try:
        if site.get("feed_url"):
            all_articles.extend(scrape_rss_feed(site))
        else:
            all_articles.extend(scrape_website(site))
    except Exception as e:
        logging.error(f"Error on {site['name']}: {e}")

all_articles.sort(key=lambda x: x["date"], reverse=True)

for art in all_articles:
    entry = fg.add_entry()
    entry.title(f"[{art['category']} | {art['locale']}] {art['title']}")
    entry.link(href=art["link"])
    entry.description(
        f"Source: {art['site']} | Published: {art['date'].strftime('%Y-%m-%d')} | Read more: {art['link']}"
    )
    entry.pubDate(art["date"].strftime("%a, %d %b %Y %H:%M:%S GMT"))

fg.rss_file("index.xml")
logging.info("RSS feed updated!")  

# Generate JSON file for each locale

import json
from collections import defaultdict

# Group articles by locale
grouped = defaultdict(list)
for article in all_articles:
    grouped[article["locale"]].append(article)

# Keep only the top 5 for each locale, sorted by date
output_data = {}
for locale, articles in grouped.items():
    sorted_articles = sorted(articles, key=lambda x: x["date"], reverse=True)[:5]
    output_data[locale] = [
        {
            "title": a["title"],
            "link": a["link"],
            "date": a["date"].isoformat() + "Z"
        } for a in sorted_articles
    ]

# Write to data.json
with open("data.json", "w") as f:
    json.dump(output_data, f, indent=2)

logging.info("data.json created with top 5 articles per locale.")


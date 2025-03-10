import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime
from urllib.parse import urljoin
import feedparser
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# List of websites & categories
# For sites that already have an RSS feed, include a "feed_url" key.
WEBSITES = [
    {
        "name": "Soaring Down South",
        "url": "https://soaringdownsouth.com/atlanta-hawks-news",
        "category": "NBA",
        "locale": "Atlanta Hawks",
        "limit": 10
    },
    {
        "name": "Peachtree Hoops",
        "url": "https://www.peachtreehoops.com/",
        "feed_url": "https://www.peachtreehoops.com/rss/current.xml",  # Using the site's existing RSS feed
        "category": "NBA",
        "locale": "Atlanta Hawks",
        "limit": 10
    },
    # Add more sites as needed...
]

# Initialize RSS feed
fg = FeedGenerator()
fg.title("Custom Multi-Site RSS Feed")
fg.link(href="https://starmencarnes.github.io/rss-feeds/index.xml", rel="self")
fg.description("Automatically generated RSS feed for multiple websites.")

def extract_title(article):
    """Try multiple methods to extract the article title and URL dynamically."""
    # 1️⃣ Check for <a> tag with a "title" attribute.
    link_elem = article.find("a", attrs={"title": True})
    if link_elem and link_elem.get("title"):
        return link_elem["title"], link_elem.get("href", "#")
    
    # 2️⃣ Check for an <h2> tag and then an <a> within it.
    h2_elem = article.find("h2")
    if h2_elem:
        a_tag = h2_elem.find("a")
        if a_tag:
            return a_tag.get_text(strip=True), a_tag.get("href", "#")
        return h2_elem.get_text(strip=True), "#"
    
    # 3️⃣ Check for meta tag with property "og:title".
    meta_title = article.find("meta", property="og:title")
    if meta_title and meta_title.get("content"):
        return meta_title["content"], "#"
    
    # 4️⃣ As a last resort, if the article itself is an <a> tag.
    if article.name == "a" and article.get("title"):
        return article["title"], article.get("href", "#")
    
    # 5️⃣ Default fallback.
    return "No Title", "#"

def scrape_rss_feed(site):
    """Parse an existing RSS feed using feedparser."""
    feed_url = site.get("feed_url")
    if not feed_url:
        return []
    
    logging.info(f"{site['name']}: Parsing RSS feed from {feed_url}")
    parsed_feed = feedparser.parse(feed_url)
    articles = []
    limit = site.get("limit", 10)
    
    for entry in parsed_feed.entries[:limit]:
        title = entry.get("title", "No Title")
        link = entry.get("link", "#")
        # Use feedparser's structured time if available.
        if "published_parsed" in entry and entry.published_parsed:
            pub_date_parsed = datetime(*entry.published_parsed[:6])
        elif "published" in entry:
            try:
                pub_date_parsed = datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pub_date_parsed = datetime.min
        else:
            pub_date_parsed = datetime.min
        
        articles.append({
            "title": title,
            "link": link,
            "site": site["name"],
            "category": site["category"],
            "locale": site.get("locale", "Unknown"),
            "date": pub_date_parsed
        })
    logging.info(f"{site['name']}: Parsed {len(articles)} articles from RSS feed.")
    return articles

def scrape_website(site):
    """Scrape articles from a website's HTML dynamically."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(site["url"], headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch {site['name']} at {site['url']}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    articles = []

    # Try to find <article> tags first.
    found_articles = soup.find_all("article")
    # If none found, try common <div> containers that might hold posts.
    if not found_articles:
        found_articles = soup.find_all("div", class_=lambda x: x and any(kw in x.lower() for kw in ["post", "entry", "story"]))
    # If still empty, as a last resort grab all <a> tags with href.
    if not found_articles:
        found_articles = soup.find_all("a", href=True)
    
    logging.info(f"{site['name']}: Found {len(found_articles)} candidate elements.")
    limit = site.get("limit", 10)
    
    for article in found_articles[:limit]:
        title, link = extract_title(article)
        # Build an absolute URL.
        link = urljoin(site["url"], link)
        # Extract publish date from a <time> element.
        date_elem = article.find("time")
        pub_date = date_elem["datetime"] if date_elem and date_elem.get("datetime") else "1970-01-01T00:00:00Z"
        try:
            pub_date_parsed = datetime.strptime(pub_date, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pub_date_parsed = datetime.min
        
        articles.append({
            "title": title,
            "link": link,
            "site": site["name"],
            "category": site["category"],
            "locale": site.get("locale", "Unknown"),
            "date": pub_date_parsed
        })

    logging.info(f"{site['name']}: Scraped {len(articles)} articles from HTML.")
    return articles

# Collect articles from all websites.
all_articles = []
for site in WEBSITES:
    try:
        # If the site provides an RSS feed, use that.
        if "feed_url" in site:
            articles = scrape_rss_feed(site)
        else:
            articles = scrape_website(site)
        all_articles.extend(articles)
    except Exception as e:
        logging.error(f"Error scraping {site['name']}: {e}")

# Sort articles by publish date (newest first).
all_articles.sort(key=lambda x: x["date"], reverse=True)

# Add each article as an entry to the RSS feed.
for article in all_articles:
    entry = fg.add_entry()
    entry.title(f"[{article['category']} | {article['locale']}] {article['title']}")
    entry.link(href=article["link"])
    entry.description(f"Source: {article['site']} | Published: {article['date'].strftime('%Y-%m-%d')} | Read more: {article['link']}")
    entry.pubDate(article["date"].strftime("%a, %d %b %Y %H:%M:%S GMT"))

# Save the RSS feed to XML.
fg.rss_file("index.xml")
logging.info("RSS feed updated and sorted by date!")

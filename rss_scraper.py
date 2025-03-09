import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime

# List of websites & categories
WEBSITES = [
    {"name": "Soaring Down South", "url": "https://soaringdownsouth.com/atlanta-hawks-news/", "category": "Sports"},
    # Add more sites as needed...
]

# Initialize RSS feed
fg = FeedGenerator()
fg.title("Custom Multi-Site RSS Feed")
fg.link(href="https://starmencarnes.github.io/rss-feeds/index.xml", rel="self")
fg.description("Automatically generated RSS feed for multiple websites.")

# Function to scrape a website
def scrape_website(site):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(site["url"], headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    articles = []
    for article in soup.find_all("article")[:10]:  # Limit per site
        title = article.find("h2").text.strip() if article.find("h2") else "No Title"
        link = article.find("a")["href"] if article.find("a") else "#"
        
        # Extract publish date
        date_elem = article.find("time")
        pub_date = date_elem["datetime"] if date_elem and "datetime" in date_elem.attrs else "1970-01-01T00:00:00Z"

        # Convert date for sorting
        try:
            pub_date_parsed = datetime.strptime(pub_date, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pub_date_parsed = datetime.min  # Use earliest date if format is wrong

        # Store the scraped article with metadata
        articles.append({
            "title": title,
            "link": link,
            "site": site["name"],
            "category": site["category"],
            "date": pub_date_parsed
        })

    return articles

# Loop through websites and collect articles
all_articles = []
for site in WEBSITES:
    try:
        articles = scrape_website(site)
        all_articles.extend(articles)
    except Exception as e:
        print(f"Error scraping {site['name']}: {e}")

# **Sort articles by publish date (newest first)**
all_articles.sort(key=lambda x: x["date"], reverse=True)

# Add articles to RSS feed
for article in all_articles:
    fe = fg.add_entry()
    fe.title(f"[{article['category']}] {article['title']}")
    fe.link(href=article["link"])
    fe.description(f"Source: {article['site']} | Published: {article['date'].strftime('%Y-%m-%d')} | Read more: {article['link']}")
    fe.pubDate(article["date"].strftime("%a, %d %b %Y %H:%M:%S GMT"))

# Save feed to XML
fg.rss_file("index.xml")
print("RSS feed updated and sorted by date!")

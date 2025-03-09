import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

# Website to scrape
URL = "https://soaringdownsouth.com/"

# Fetch website content
headers = {"User-Agent": "Mozilla/5.0"}
response = requests.get(URL, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

# Initialize RSS feed
fg = FeedGenerator()
fg.title("Soaring Down South - Custom RSS Feed")
fg.link(href=URL, rel="self")
fg.description("Automatically generated RSS feed for Soaring Down South")

# Find articles (adjust if needed)
for article in soup.find_all("article")[:10]:  # Limit to latest 10
    title = article.find("h2").text.strip() if article.find("h2") else "No Title"
    link = article.find("a")["href"] if article.find("a") else "#"

    fe = fg.add_entry()
    fe.title(title)
    fe.link(href=link)
    fe.description(f"Read more: {link}")

# Save feed to XML
fg.rss_file("rss_feed.xml")
print("RSS feed updated!")

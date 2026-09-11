import os
import glob
from datetime import datetime, timezone
import frontmatter
import markdown
from feedgen.feed import FeedGenerator

BASE_URL = "https://karlbishnu.github.io/spark-feed"
AUTHOR_NAME = "커피농장"
CATEGORIES = {
    "all": "Spark Feed - All Updates",
    "ai": "Spark Feed - AI & Dev",
    "astrophysics": "Spark Feed - Astrophysics & Space",
    "macro": "Spark Feed - Macroeconomics"
}

def create_feed(category_id, title, posts):
    fg = FeedGenerator()
    feed_url = f"{BASE_URL}/{category_id}.xml"
    site_url = f"{BASE_URL}/"
    
    fg.id(feed_url)
    fg.title(title)
    fg.author({"name": AUTHOR_NAME})
    fg.link(href=site_url, rel="alternate")
    fg.link(href=feed_url, rel="self")
    fg.description(f"Curated feed for {title}")
    fg.language("ko")

    for post_date, post, file_path in posts[:20]:
        fe = fg.add_entry()
        title_text = post.get("title", os.path.splitext(os.path.basename(file_path))[0])
        link = post.get("link", site_url)
        
        fe.id(f"{feed_url}#{os.path.basename(file_path)}")
        fe.title(title_text)
        fe.link(href=link)
        fe.pubDate(post_date)
        
        html_content = markdown.markdown(post.content)
        fe.description(html_content)

    os.makedirs("public", exist_ok=True)
    fg.rss_file(f"public/{category_id}.xml", pretty=True)

category_posts = {cat: [] for cat in CATEGORIES if cat != "all"}
all_posts = []

for file_path in glob.glob("content/**/*.md", recursive=True):
    post = frontmatter.load(file_path)
    post_date = post.get("date")
    if not isinstance(post_date, datetime):
        post_date = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)
    elif post_date.tzinfo is None:
        post_date = post_date.replace(tzinfo=timezone.utc)
    
    item = (post_date, post, file_path)
    all_posts.append(item)
    
    parent_dir = os.path.basename(os.path.dirname(file_path))
    if parent_dir in category_posts:
        category_posts[parent_dir].append(item)

all_posts.sort(key=lambda x: x[0], reverse=True)
for cat in category_posts:
    category_posts[cat].sort(key=lambda x: x[0], reverse=True)

create_feed("all", CATEGORIES["all"], all_posts)
for cat, posts in category_posts.items():
    create_feed(cat, CATEGORIES[cat], posts)

print("Feeds generated successfully.")

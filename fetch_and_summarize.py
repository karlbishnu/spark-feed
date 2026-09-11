import datetime
import os
import urllib.request
import xml.etree.ElementTree as ET
from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

today_str = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d")

def summarize_and_save(category, title, source_text, source_link):
    prompt = f"""
    아래 내용을 한국어로 간결하게 요약해줘.
    핵심 내용 3줄 불릿 포인트와 시사점 1줄로 작성해.

    [내용]
    {source_text[:3000]}
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    content = f"""---
title: "{title}"
date: {datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()}
link: "{source_link}"
---

{response.text}
"""
    file_path = f"content/{category}/{today_str}-{category}.md"
    os.makedirs(f"content/{category}", exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Saved: {file_path}")

# 예시 1: 천체물리 (arXiv astro-ph 최신 피드 파싱)
try:
    req = urllib.request.Request("https://rss.arxiv.org/rss/astro-ph", headers={'User-Agent': 'Mozilla/5.0'})
    xml_data = urllib.request.urlopen(req).read()
    root = ET.fromstring(xml_data)
    first_item = root.find(".//item")
    if first_item is not None:
        p_title = first_item.find("title").text.strip()
        p_desc = first_item.find("description").text.strip()
        p_link = first_item.find("link").text.strip()
        summarize_and_save("astrophysics", f"[arXiv] {p_title}", p_desc, p_link)
except Exception as e:
    print(f"Astrophysics fetch error: {e}")
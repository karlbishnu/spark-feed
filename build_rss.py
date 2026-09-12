import os
import re
import glob
from datetime import datetime, timezone
import frontmatter
import markdown
from feedgen.feed import FeedGenerator

REPO_NAME = "spark-feed"
GITHUB_USER = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
SITE_URL = f"https://{GITHUB_USER}.github.io/{REPO_NAME}" if GITHUB_USER else f"https://localhost/{REPO_NAME}"

CATEGORY_CONFIG = {
    "astrophysics": {"name": "천체물리", "color": "#7c3aed", "bg": "#f5f3ff", "icon": "🔭"},
    "macro":        {"name": "거시경제", "color": "#059669", "bg": "#ecfdf5", "icon": "📈"},
    "ai":           {"name": "AI·기술",   "color": "#2563eb", "bg": "#eff6ff", "icon": "🤖"}
}

def clean_latex_to_unicode(text: str) -> str:
    """RSS 리더기에서 깨지는 LaTeX 수식을 자연스러운 유니코드 텍스트로 변환"""
    replacements = [
        (r'\\Lambda\\text\{CDM\}|\\Lambda\s*CDM|\$\\Lambda\\text\{CDM\}\$', 'ΛCDM'),
        (r'\\text\{--\}|\\text\{—\}', '–'),
        (r'\\text\{(\w+)\}', r'\1'),
        (r'\\mu\\text\{m\}|\\mu\s*m|\\mu', 'μm'),
        (r'\\sim', '~'),
        (r'\\approx', '≈'),
        (r'\\pm', '±'),
        (r'\\times', '×'),
        (r'\\gtrsim', '≳'),
        (r'\\lesssim', '≲'),
        (r'\\odot', '☉'),
        (r'M_\\odot|M_\{\\odot\}', 'M☉'),
        (r'\\beta', 'β'),
        (r'\\epsilon', 'ϵ'),
        (r'\\lambda', 'λ'),
        (r'\$([^\$]+)\$', r'\1'),  # 인라인 $수식$의 $ 기호 제거
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    return text

def parse_post(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        raw = f.read()

    # 줄바꿈 깨진 frontmatter 정규식 복구
    meta = {}
    content = raw

    fm_match = re.match(r'^---\s*(.*?)\s*---\s*(.*)$', raw, re.DOTALL)
    if fm_match:
        header_text = fm_match.group(1)
        content = fm_match.group(2)
        for k in ["category", "title", "date", "link"]:
            m = re.search(rf'{k}:\s*"?(.*?)"?(?=\s+(?:category|title|date|link):|$)', header_text)
            if m:
                meta[k] = m.group(1).strip()
    else:
        try:
            post = frontmatter.loads(raw)
            meta = post.metadata
            content = post.content
        except Exception:
            pass

    # 본문 첫머리에 남은 # 제목 제거 (중복 노출 방지)
    content = re.sub(r'^#\s+.*?\n', '', content.strip())
    content = clean_latex_to_unicode(content)

    title = meta.get("title")
    if not title:
        first_line = content.strip().split("\n")[0]
        title = re.sub(r'^[#\s]+', '', first_line)[:60] or os.path.basename(file_path)

    category = meta.get("category", "ai").lower()
    link = meta.get("link", SITE_URL)
    
    date_str = meta.get("date")
    try:
        post_date = datetime.fromisoformat(date_str) if date_str else datetime.now(timezone.utc)
    except Exception:
        post_date = datetime.now(timezone.utc)

    return {
        "title": title,
        "category": category,
        "date": post_date,
        "link": link,
        "content": content
    }

def format_html_content(post_data):
    """Feedly 가독성을 극대화하는 인라인 CSS 주입"""
    cat = post_data["category"]
    conf = CATEGORY_CONFIG.get(cat, {"name": cat.upper(), "color": "#4b5563", "bg": "#f3f4f6", "icon": "📌"})
    
    # 마크다운 -> HTML 변환
    body_html = markdown.markdown(
        post_data["content"],
        extensions=["tables", "fenced_code", "nl2br"]
    )

    # 헤더 및 테이블 디자인 인라인 패치
    body_html = re.sub(
        r'<h3>(.*?)</h3>',
        rf'<h3 style="border-left: 4px solid {conf["color"]}; padding-left: 10px; margin-top: 24px; margin-bottom: 12px; font-size: 1.15em; color: #1e293b;">\1</h3>',
        body_html
    )
    body_html = body_html.replace(
        '<table>',
        '<table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.95em;">'
    ).replace(
        '<th>',
        '<th style="border: 1px solid #e2e8f0; background: #f8fafc; padding: 8px 12px; font-weight: 600; text-align: left;">'
    ).replace(
        '<td>',
        '<td style="border: 1px solid #e2e8f0; padding: 8px 12px;">'
    )

    styled_html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Pretendard', sans-serif; line-height: 1.7; color: #334155;">
      <!-- 카테고리 뱃지 -->
      <div style="margin-bottom: 16px;">
        <span style="display: inline-block; background-color: {conf['bg']}; color: {conf['color']}; border: 1px solid {conf['color']}40; padding: 4px 10px; border-radius: 9999px; font-size: 0.82em; font-weight: 600;">
          {conf['icon']} {conf['name']}
        </span>
      </div>

      <!-- 요약 본문 -->
      <div>
        {body_html}
      </div>

      <!-- 원문 출처 바로가기 버튼 -->
      <div style="margin-top: 28px; padding-top: 16px; border-top: 1px dashed #cbd5e1;">
        <a href="{post_data['link']}" target="_blank" style="display: inline-block; background-color: {conf['color']}; color: #ffffff; text-decoration: none; padding: 8px 16px; border-radius: 6px; font-size: 0.9em; font-weight: 500;">
          원문 출처 / 논문 보기 →
        </a>
      </div>
    </div>
    """
    return styled_html

def main():
    os.makedirs("public", exist_ok=True)
    post_files = glob.glob("content/**/*.md", recursive=True)
    
    posts = [parse_post(f) for f in post_files]
    posts.sort(key=lambda x: x["date"], reverse=True)

    # 1. 전체 통합 피드 생성
    fg_all = FeedGenerator()
    fg_all.id(f"{SITE_URL}/all.xml")
    fg_all.title("Spark Feed - All Updates")
    fg_all.description("AI, 천체물리, 거시경제 맞춤 큐레이션 피드")
    fg_all.link(href=SITE_URL)

    for p in posts:
        fe = fg_all.add_entry()
        fe.id(f"{p['link']}#{p['date'].strftime('%Y%m%d%H%M')}")
        fe.title(p["title"])
        fe.link(href=p["link"])
        fe.published(p["date"])
        fe.content(format_html_content(p), type="CDATA")

    fg_all.rss_file("public/all.xml")

    # 2. 분야별 개별 피드 생성
    for cat in ["astrophysics", "macro", "ai"]:
        cat_posts = [p for p in posts if p["category"] == cat]
        conf = CATEGORY_CONFIG.get(cat, {"name": cat})
        
        fg_cat = FeedGenerator()
        fg_cat.id(f"{SITE_URL}/{cat}.xml")
        fg_cat.title(f"Spark Feed - {conf['name']}")
        fg_cat.description(f"{conf['name']} 최신 요약 피드")
        fg_cat.link(href=f"{SITE_URL}/{cat}.xml")

        for p in cat_posts:
            fe = fg_cat.add_entry()
            fe.id(f"{p['link']}#{p['date'].strftime('%Y%m%d%H%M')}")
            fe.title(p["title"])
            fe.link(href=p["link"])
            fe.published(p["date"])
            fe.content(format_html_content(p), type="CDATA")

        fg_cat.rss_file(f"public/{cat}.xml")
    
    print("Successfully built RSS feeds with enhanced Feedly styling.")

    # 루트 접속 시 404 방지용 index.html 자동 생성
    index_html = f"""<!DOCTYPE html>
        <html lang="ko">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Spark Feed Directory</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Pretendard', sans-serif; max-width: 600px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #1e293b; background: #f8fafc; }}
            h1 {{ font-size: 1.5rem; margin-bottom: 8px; }}
            p.desc {{ color: #64748b; font-size: 0.95rem; margin-top: 0; }}
            ul {{ list-style: none; padding: 0; margin-top: 24px; }}
            li {{ background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }}
            a.feed-link {{ font-weight: 600; text-decoration: none; color: #2563eb; }}
            a.feedly-btn {{ font-size: 0.85rem; background: #22c55e; color: white; padding: 4px 10px; border-radius: 4px; text-decoration: none; font-weight: 500; }}
        </style>
        </head>
        <body>
        <h1>📡 Spark Feed</h1>
        <p class="desc">자동 리서치 큐레이션 RSS 피드 목록</p>
        <ul>
            <li>
            <a class="feed-link" href="{SITE_URL}/all.xml">전체 통합 피드 (all.xml)</a>
            <a class="feedly-btn" href="https://feedly.com/i/subscription/feed/{SITE_URL}/all.xml" target="_blank">+ Feedly</a>
            </li>
            <li>
            <a class="feed-link" href="{SITE_URL}/astrophysics.xml">🔭 천체물리 (astrophysics.xml)</a>
            <a class="feedly-btn" href="https://feedly.com/i/subscription/feed/{SITE_URL}/astrophysics.xml" target="_blank">+ Feedly</a>
            </li>
            <li>
            <a class="feed-link" href="{SITE_URL}/macro.xml">📈 거시경제 (macro.xml)</a>
            <a class="feedly-btn" href="https://feedly.com/i/subscription/feed/{SITE_URL}/macro.xml" target="_blank">+ Feedly</a>
            </li>
            <li>
            <a class="feed-link" href="{SITE_URL}/ai.xml">🤖 AI·기술 (ai.xml)</a>
            <a class="feedly-btn" href="https://feedly.com/i/subscription/feed/{SITE_URL}/ai.xml" target="_blank">+ Feedly</a>
            </li>
        </ul>
        </body>
        </html>"""

    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

if __name__ == "__main__":
    main()
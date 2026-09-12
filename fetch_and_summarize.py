import io
import json
import os
import re
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# 1. 구글 드라이브에서 _topics.md 읽기
def get_topics_config():
    sa_info = json.loads(os.environ["GCP_SA_KEY"])
    raw_folder_id = os.environ["DRIVE_FOLDER_ID"].strip().strip('"').strip("'")
    if "drive.google.com" in raw_folder_id:
        m = re.search(r'folders/([a-zA-Z0-9_-]+)', raw_folder_id)
        folder_id = m.group(1) if m else raw_folder_id
    else:
        folder_id = raw_folder_id.split("?")[0]

    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    service = build("drive", "v3", credentials=creds)

    res = service.files().list(
        q=f"'{folder_id}' in parents and name = '_topics.md' and trashed = false",
        fields="files(id, mimeType)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    files = res.get("files", [])
    if not files:
        raise FileNotFoundError("Google Drive의 spark-feed 폴더에서 _topics.md를 찾을 수 없습니다.")

    f_id = files[0]["id"]
    mime = files[0]["mimeType"]
    if mime == "application/vnd.google-apps.document":
        req = service.files().export_media(fileId=f_id, mimeType="text/plain")
    else:
        req = service.files().get_media(fileId=f_id, supportsAllDrives=True)

    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    return fh.getvalue().decode("utf-8")

# 2. _topics.md에서 카테고리 블록 파싱
def parse_categories(topics_text):
    categories = {}
    sections = re.split(r'\n(?=##\s+)', topics_text)
    for sec in sections:
        header_match = re.match(r'##\s+(?:\d+\.\s*)?([a-zA-Z0-9_-]+)', sec)
        if header_match:
            slug = header_match.group(1).strip().lower()
            categories[slug] = sec.strip()
    return categories

# 3. Gemini 3.8 Flash 호출 (Search Grounding 활성화)
def generate_post(client, category, rules):
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    today_str = now.strftime("%Y-%m-%d")
    iso_date = now.isoformat()

    system_instruction = """
    당신은 테크 및 학술 동향 전문 큐레이터입니다.
    사용자가 지정한 카테고리와 규칙에 맞춰 지난 24~48시간 동안 발표된 가장 중요하고 권위 있는 최신 1차 정보(논문, 지표, 모델 릴리즈)를 웹 검색으로 조사하여 마크다운 문서를 작성합니다.

    [작성 규칙]
    1. 최상단은 반드시 규격에 맞는 YAML Frontmatter로 시작할 것 (각 항목 줄바꿈 필수).
    2. Feedly RSS 호환을 위해 LaTeX($...$, \\approx 등) 문법을 절대 쓰지 말고, 유니코드 기호(≈, ±, M☉, ΛCDM 등)로 작성할 것.
    3. 거시경제 등 시각화가 필요한 경우 공백 없는 QuickChart 이미지 URL을 본문에 포함할 것.
    """

    prompt = f"""
    [요청 카테고리: {category}]
    [오늘 날짜: {today_str}]

    다음 설정 규칙을 엄격히 따라 최신 뉴스를 조사하고 마크다운 문서를 완성하세요:
    {rules}

    [필수 메타데이터 서식]
    ---
    category: {category}
    title: "<핵심 요약 제목>"
    date: {iso_date}
    link: "<실제 원문 출처 URL>"
    ---

    [주의] 텍스트 외 코드 블록(```markdown ... ```)으로 전체를 감싸지 말고 마크다운 본문을 바로 출력하세요.
    """

    resp = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[{"google_search": {}}],
            temperature=0.2,
        )
    )
    return resp.text, today_str

def main():
    topics_text = get_topics_config()
    categories = parse_categories(topics_text)
    if not categories:
        print("경고: _topics.md에서 파싱된 카테고리가 없습니다.")
        return

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    for cat, rules in categories.items():
        print(f"[{cat}] 리서치 및 요약 생성 시작...")
        try:
            content, today_str = generate_post(client, cat, rules)
            content = re.sub(r'^```(?:markdown)?\s*', '', content.strip())
            content = re.sub(r'\s*```$', '', content)

            target_dir = f"content/{cat}"
            os.makedirs(target_dir, exist_ok=True)
            target_path = f"{target_dir}/{today_str}-{cat}.md"

            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"성공: {target_path}")
        except Exception as e:
            print(f"실패 [{cat}]: {e}")

if __name__ == "__main__":
    main()
import io
import json
import os
import re
import frontmatter
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SERVICE_ACCOUNT_INFO = json.loads(os.environ["GCP_SA_KEY"])
FOLDER_ID = os.environ["DRIVE_FOLDER_ID"]

creds = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=["https://www.googleapis.com/auth/drive.readonly"]
)
service = build("drive", "v3", credentials=creds)

# 지정된 폴더 내 파일 목록 조회
results = service.files().list(
    q=f"'{FOLDER_ID}' in parents and trashed = false",
    fields="files(id, name, mimeType, modifiedTime)"
).execute()
files = results.get("files", [])

for file in files:
    file_id = file["id"]
    name = file["name"]
    mime_type = file["mimeType"]

    # 설정 파일(_로 시작)은 피드 발행 대상에서 제외
    if name.startswith("_"):
        continue
    
    # Google Docs 형식인 경우 텍스트로 내보내기, 일반 파일은 직접 다운로드
    if mime_type == "application/vnd.google-apps.document":
        request = service.files().export_media(fileId=file_id, mimeType="text/plain")
    else:
        request = service.files().get_media(fileId=file_id)
        
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
        
    raw_text = fh.getvalue().decode("utf-8")
    
    # 프론트매터 파싱 및 카테고리 판별
    try:
        post = frontmatter.loads(raw_text)
        category = post.get("category", "").lower()
        if category not in ["ai", "astrophysics", "macro"]:
            # 카테고리 미지정 시 제목/본문 키워드 기반 기본 분류
            if any(k in raw_text.lower() for k in ["arxiv", "telescope", "hubble", "jwst", "cosmology"]):
                category = "astrophysics"
            elif any(k in raw_text.lower() for k in ["cpi", "fomc", "금리", "fed", "macro"]):
                category = "macro"
            else:
                category = "ai"
                
        # 파일명 정규화 (.md 확장자 부여)
        safe_name = re.sub(r'[^a-zA-Z0-9가-힣_-]', '_', os.path.splitext(name)[0])
        target_path = f"content/{category}/{safe_name}.md"
        os.makedirs(f"content/{category}", exist_ok=True)
        
        with open(target_path, "w", encoding="utf-8") as out:
            out.write(raw_text)
        print(f"Synced: {target_path}")
    except Exception as e:
        print(f"Failed to process {name}: {e}")
import hashlib
import os
import re
from urllib.parse import urljoin

import mysql.connector
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "douner-db"),
    "user": os.getenv("MYSQL_USER", "douner"),
    "password": os.getenv("MYSQL_PASSWORD", "1234"),
    "database": os.getenv("MYSQL_DATABASE", "douner_ref"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DounerRAGBot/1.0)"
}

ACADEMIC_PAGES = [
    {
        "category": "학사",
        "title": "동아대학교 학사 공지사항",
        "url": "https://www.donga.ac.kr/kor/CMS/Board/Board.do?mCode=MN171&robot=Y",
    },
    {
        "category": "수강신청",
        "title": "동아대학교 수강신청 신편입생 로그인 안내",
        "url": "https://dxsugang.donga.ac.kr/login",
    },
    {
        "category": "컴퓨터공학과",
        "title": "컴퓨터공학과 교과과정표",
        "url": "https://computer.donga.ac.kr/computer/CMS/Contents/Contents.do?mCode=MN022",
    },
    {
        "category": "컴퓨터공학과",
        "title": "컴퓨터공학과 학과안내",
        "url": "https://computer.donga.ac.kr/computer/CMS/Contents/Contents.do?mCode=MN020",
    },
    {
        "category": "진로",
        "title": "컴퓨터공학과 졸업후진로",
        "url": "https://computer.donga.ac.kr/computer/CMS/Contents/Contents.do?mCode=MN021",
    },
    {
        "category": "편입생",
        "title": "동아대학교 편입생제도",
        "url": "https://dms.donga.ac.kr/envu/3616/subview.do",
    },
]


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_page_content(text: str) -> str:
    remove_keywords = [
        "스킵네비게이션",
        "본문바로가기",
        "주메뉴바로가기",
        "메인으로 이동",
        "SNS 목록열기",
        "SNS 목록닫기",
        "FACEBOOK 공유하기",
        "TWITTER 공유하기",
        "BLOG 공유하기",
        "Adobe Reader 설치하기",
        "스크롤 상단으로",
        "스크롤 하단으로",
        "개인정보처리방침",
        "캠퍼스맵",
    ]

    for keyword in remove_keywords:
        text = text.replace(keyword, " ")

    text = re.sub(r"COPYRIGHT\(C\).*?RESERVED\.?", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_hash(url: str, content: str) -> str:
    return hashlib.sha256(f"{url}|{content}".encode("utf-8")).hexdigest()


def get_conn():
    return mysql.connector.connect(**DB_CONFIG)


def ensure_documents_table(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category VARCHAR(50),
            title VARCHAR(255) NOT NULL UNIQUE,
            content LONGTEXT,
            url VARCHAR(1024),
            source VARCHAR(100) DEFAULT 'manual',
            content_hash CHAR(64),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_documents_category (category),
            INDEX idx_documents_source (source)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """
    )

    for column, ddl in {
        "url": "ALTER TABLE documents ADD COLUMN url VARCHAR(1024)",
        "source": "ALTER TABLE documents ADD COLUMN source VARCHAR(100) DEFAULT 'manual'",
        "content_hash": "ALTER TABLE documents ADD COLUMN content_hash CHAR(64)",
        "updated_at": (
            "ALTER TABLE documents ADD COLUMN updated_at TIMESTAMP "
            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        ),
    }.items():
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'documents'
              AND COLUMN_NAME = %s
            """,
            (column,),
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(ddl)

    conn.commit()
    cursor.close()


def fetch_page(page):
    print(f"📡 요청 URL: {page['url']}")
    res = requests.get(page["url"], headers=HEADERS, timeout=20)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    title = page["title"]
    h1_or_h2 = soup.select_one("h1, h2, h3")
    if h1_or_h2:
        found_title = clean_text(h1_or_h2.get_text(" "))
        if found_title and len(found_title) <= 80:
            title = f"{page['title']} - {found_title}"

    candidates = [
        "#contents",
        ".contents",
        ".content",
        ".cont",
        ".subContent",
        ".board_view",
        ".view_cont",
        "main",
        "body",
    ]

    content = ""
    for selector in candidates:
        el = soup.select_one(selector)
        if not el:
            continue
        text = clean_page_content(el.get_text(" "))
        if len(text) > len(content):
            content = text

    if not content:
        content = clean_page_content(soup.get_text(" "))

    absolute_links = []
    for a in soup.select("a[href]"):
        label = clean_text(a.get_text(" "))
        href = a.get("href", "")
        if label and href and any(k in label for k in ["PDF", "다운로드", "학사", "졸업", "편입"]):
            absolute_links.append(f"{label}: {urljoin(page['url'], href)}")

    if absolute_links:
        content = f"{content}\n\n관련 링크:\n" + "\n".join(absolute_links[:20])

    return title, content


def save_document(conn, category, title, content, url):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO documents (category, title, content, url, source, content_hash)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            category = VALUES(category),
            content = VALUES(content),
            url = VALUES(url),
            source = VALUES(source),
            content_hash = VALUES(content_hash),
            updated_at = CURRENT_TIMESTAMP
        """,
        (category, title, content, url, "academic_page", make_hash(url, content)),
    )
    conn.commit()
    cursor.close()


def main():
    conn = get_conn()
    ensure_documents_table(conn)

    saved = 0
    for page in ACADEMIC_PAGES:
        try:
            title, content = fetch_page(page)
            if len(content) < 100:
                print(f"⚠️ 본문 짧음 스킵: {page['title']}")
                continue

            save_document(conn, page["category"], title, content, page["url"])
            saved += 1
            print(f"✅ 저장 완료: {title}")
        except Exception as e:
            print(f"❌ 실패: {page['title']} / {e}")

    conn.close()
    print(f"🎉 학사 정적 페이지 저장 완료: {saved}건")


if __name__ == "__main__":
    main()

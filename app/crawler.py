import os
import re
import hashlib
import requests
import mysql.connector
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "douner-db"),
    "user": os.getenv("MYSQL_USER", "douner"),
    "password": os.getenv("MYSQL_PASSWORD", "1234"),
    "database": os.getenv("MYSQL_DATABASE", "douner_ref"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
}

TARGETS = [
    {
        "source": "donga_academic_notice",
        "category": "학사",
        "base_url": "https://www.donga.ac.kr",
        "list_url": "https://www.donga.ac.kr/kor/CMS/Board/Board.do?mCode=MN171&page=1&robot=Y",
    },
    {
        "source": "donga_global_notice",
        "category": "유학생",
        "base_url": "https://global.donga.ac.kr",
        "list_url": "https://global.donga.ac.kr/global/CMS/Board/Board.do?mCode=MN066",
    },
    {
        "source": "computer_notice",
        "category": "컴퓨터공학과",
        "base_url": "https://computer.donga.ac.kr",
        "list_url": "https://computer.donga.ac.kr/computer/CMS/Board/Board.do?mCode=MN044",
    },
    {
        "source": "computer_job",
        "category": "취업정보",
        "base_url": "https://computer.donga.ac.kr",
        "list_url": "https://computer.donga.ac.kr/computer/CMS/Board/Board.do?mCode=MN045",
    },
    {
        "source": "computer_competition",
        "category": "대회정보",
        "base_url": "https://computer.donga.ac.kr",
        "list_url": "https://computer.donga.ac.kr/computer/CMS/Board/Board.do?mCode=MN046",
    },
    {
        "source": "computer_education",
        "category": "교육정보",
        "base_url": "https://computer.donga.ac.kr",
        "list_url": "https://computer.donga.ac.kr/computer/CMS/Board/Board.do?mCode=MN047",
    },
]

ACADEMIC_CONTENT_PAGES = [
    {
        "source": "donga_graduation_requirements",
        "category": "졸업",
        "title": "졸업기준 안내",
        "url": "https://www.donga.ac.kr/kor/CMS/Contents/Contents.do?mCode=MN137",
    },
    {
        "source": "donga_graduation_thesis",
        "category": "졸업논문",
        "title": "졸업논문 안내",
        "url": "https://www.donga.ac.kr/kor/CMS/Contents/Contents.do?mCode=MN138",
    },
    {
        "source": "donga_degree_completion_deferment",
        "category": "학사학위취득유예",
        "title": "학사학위취득 유예 안내",
        "url": "https://www.donga.ac.kr/kor/CMS/Contents/Contents.do?mCode=MN139",
    },
    {
        "source": "donga_early_graduation",
        "category": "조기졸업",
        "title": "조기졸업 안내",
        "url": "https://www.donga.ac.kr/kor/CMS/Contents/Contents.do?mCode=MN140",
    },
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DounerRAGBot/1.0)"
}


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_hash(title: str, url: str, content: str) -> str:
    raw = f"{title}|{url}|{content}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_conn():
    return mysql.connector.connect(**DB_CONFIG)


def ensure_notices_table():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notices (
            id INT AUTO_INCREMENT PRIMARY KEY,
            source VARCHAR(100) NOT NULL,
            category VARCHAR(50),
            title VARCHAR(255) NOT NULL,
            content LONGTEXT,
            url VARCHAR(1024) NOT NULL,
            published_at VARCHAR(30),
            content_hash CHAR(64) NOT NULL UNIQUE,
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_notices_url (url),
            INDEX idx_notices_source (source),
            INDEX idx_notices_category (category)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """)

    for column, ddl in {
        "source": "ALTER TABLE notices ADD COLUMN source VARCHAR(100) NOT NULL DEFAULT 'unknown'",
        "category": "ALTER TABLE notices ADD COLUMN category VARCHAR(50)",
        "title": "ALTER TABLE notices ADD COLUMN title VARCHAR(255) NOT NULL DEFAULT ''",
        "content": "ALTER TABLE notices ADD COLUMN content LONGTEXT",
        "url": "ALTER TABLE notices ADD COLUMN url VARCHAR(1024) NOT NULL DEFAULT ''",
        "published_at": "ALTER TABLE notices ADD COLUMN published_at VARCHAR(30)",
        "content_hash": "ALTER TABLE notices ADD COLUMN content_hash CHAR(64)",
        "crawled_at": "ALTER TABLE notices ADD COLUMN crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }.items():
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'notices'
              AND COLUMN_NAME = %s
            """,
            (column,)
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(ddl)

    conn.commit()
    cursor.close()
    conn.close()


def save_notice(source, category, title, content, url, published_at=None):
    content_hash = make_hash(title, url, content)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM notices WHERE url = %s LIMIT 1", (url,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            """
            UPDATE notices
            SET source = %s,
                category = %s,
                title = %s,
                content = %s,
                published_at = %s,
                content_hash = %s,
                crawled_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (source, category, title, content, published_at, content_hash, existing[0])
        )
    else:
        cursor.execute(
            """
            INSERT INTO notices
            (source, category, title, content, url, published_at, content_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (source, category, title, content, url, published_at, content_hash)
        )

    conn.commit()
    cursor.close()
    conn.close()


def extract_notice_links(target):
    print(f"📡 요청 URL: {target['list_url']}")

    res = requests.get(target["list_url"], headers=HEADERS, timeout=15)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    links = []

    for a in soup.select("a[href]"):
        title = clean_text(a.get_text(" "))
        href = a.get("href", "")

        if not href:
            continue

        # 게시글 상세 링크 조건
        # 예: ?mCode=MN066&mode=view&mgr_seq=717&board_seq=8448840
        if "mode=view" not in href:
            continue

        if "board_seq=" not in href:
            continue

        if not title or len(title) < 5:
            continue

        blacklist = [
            "로그인", "사이트맵", "전체", "검색", "목록",
            "이전", "다음", "스크롤", "개인정보처리방침",
            "캠퍼스맵"
        ]

        if any(b in title for b in blacklist):
            continue

        url = urljoin(target["list_url"], href)

        links.append({
            "title": title,
            "url": url
        })

    unique = []
    seen = set()

    for item in links:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        unique.append(item)

    print("🔍 추출된 링크 미리보기")
    for item in unique[:10]:
        print("-", item["title"][:80], item["url"])

    return unique[:30]

def extract_detail_content(url):
    res = requests.get(url, headers=HEADERS, timeout=15)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    # 불필요한 태그 제거
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    title = ""

    h3 = soup.select_one("h3")
    if h3:
        title = clean_text(h3.get_text())

    # 게시글 본문 후보
    candidates = [
        ".view_cont",
        ".board_view",
        ".viewContent",
        ".contents",
        ".cont",
        "#contents",
        "body"
    ]

    content = ""

    for selector in candidates:
        el = soup.select_one(selector)
        if el:
            text = clean_text(el.get_text(" "))
            if len(text) > len(content):
                content = text

    if not content:
        content = clean_text(soup.get_text(" "))

    content = clean_notice_content(content)

    # 날짜 후보
    published_at = None
    date_match = re.search(r"20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2}", content)
    if date_match:
        published_at = date_match.group(0)

    return title, content, published_at

def extract_academic_content_page(page):
    print(f"📘 학사안내 페이지 요청: {page['url']}")

    res = requests.get(page["url"], headers=HEADERS, timeout=15)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    title = page["title"]
    title_el = soup.select_one("h1, h2, h3, .pageTitle, .contTitle")
    if title_el:
        found_title = clean_text(title_el.get_text(" "))
        if found_title and len(found_title) <= 80:
            title = found_title

    candidates = [
        "#contents",
        ".contents",
        ".content",
        ".cont",
        ".subContent",
        "main",
        "body",
    ]

    content = ""
    for selector in candidates:
        el = soup.select_one(selector)
        if not el:
            continue
        text = clean_academic_content(el.get_text(" "), title)
        if len(text) > len(content):
            content = text

    if not content:
        content = clean_academic_content(soup.get_text(" "), title)

    related_links = []
    for a in soup.select("a[href]"):
        label = clean_text(a.get_text(" "))
        href = a.get("href", "")
        if label and href and any(k in label for k in ["다운로드", "PDF", "졸업", "학사", "신청"]):
            related_links.append(f"{label}: {urljoin(page['url'], href)}")

    if related_links:
        content = f"{content}\n\n관련 링크:\n" + "\n".join(related_links[:20])

    return title, content


def crawl_academic_content_pages():
    print("🚀 졸업 관련 학사안내 페이지 크롤링 시작")
    saved = 0

    for page in ACADEMIC_CONTENT_PAGES:
        try:
            title, content = extract_academic_content_page(page)

            if len(content) < 100:
                print(f"⚠️ 본문 짧음 스킵: {page['title']}")
                continue

            save_notice(
                source=page["source"],
                category=page["category"],
                title=title,
                content=content,
                url=page["url"],
                published_at=None,
            )

            saved += 1
            print(f"✅ 저장 완료: {title}")
        except Exception as e:
            print(f"❌ 실패: {page['title']} / {e}")

    print(f"🎉 졸업 관련 학사안내 페이지 저장 완료: {saved}건")


def crawl_target(target):
    print(f"🚀 크롤링 시작: {target['source']}")

    links = extract_notice_links(target)
    print(f"🔗 후보 링크 {len(links)}개 발견")

    saved = 0

    for item in links:
        try:
            detail_title, content, published_at = extract_detail_content(item["url"])

            title = detail_title if detail_title else item["title"]

            if len(content) < 100:
                print(f"⚠️ 본문 짧음 스킵: {title}")
                continue

            save_notice(
                source=target["source"],
                category=target["category"],
                title=title,
                content=content,
                url=item["url"],
                published_at=published_at
            )

            saved += 1
            print(f"✅ 저장 완료: {title}")

        except Exception as e:
            print(f"❌ 실패: {item['title']} / {e}")

    print(f"🎉 {target['source']} 저장 완료: {saved}건")


def clean_notice_content(text: str) -> str:
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
        "인쇄",
        "url 복사",
        "저작권 등 다른 사람의 권리를 침해하거나",
        "이용약관 및 관련법률에 의해 제재를 받으실 수 있습니다",
        "목록",
    ]

    for keyword in remove_keywords:
        text = text.replace(keyword, " ")

    # 이전글/다음글 이후 불필요한 부분 일부 제거
    text = re.sub(r"이전글\s+.*?(?=본문:|$)", " ", text)
    text = re.sub(r"다음글\s+.*?(?=본문:|$)", " ", text)

    # 공백 정리
    text = re.sub(r"\s+", " ", text).strip()

    return text




def clean_academic_content(text: str, title: str) -> str:
    text = clean_notice_content(text)

    remove_keywords = [
        "전체메뉴열기",
        "전체메뉴닫기",
        "통합검색 SEARCH",
        "통합검색 닫기",
        "LOGIN",
        "로그인",
        "사이트맵",
        "DONG-A UNIVERSITY",
        "동아대학교",
        "개인정보처리방침",
        "이메일주소무단수집거부",
    ]

    for keyword in remove_keywords:
        text = text.replace(keyword, " ")

    title_positions = [match.start() for match in re.finditer(re.escape(title), text)]
    if title_positions:
        text = text[title_positions[-1]:]

    text = re.sub(r"COPYRIGHT\(C\).*?RESERVED\.?,?", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def main():
    ensure_notices_table()

    for target in TARGETS:
        crawl_target(target)

    crawl_academic_content_pages()


if __name__ == "__main__":
    main()

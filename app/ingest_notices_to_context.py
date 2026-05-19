import os
import hashlib
import mysql.connector
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "db"),
    "user": os.getenv("MYSQL_USER", "douner"),
    "password": os.getenv("MYSQL_PASSWORD", "1234"),
    "database": os.getenv("MYSQL_DATABASE", "douner_ref"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
}


def make_hash(source_type: str, source_id: int, title: str, chunk_text: str, chunk_index: int) -> str:
    raw = f"{source_type}|{source_id}|{title}|{chunk_index}|{chunk_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, source, category, title, content, url, published_at
        FROM notices
        WHERE content IS NOT NULL AND content != ''
    """)

    notices = cursor.fetchall()
    print(f"📦 notices {len(notices)}건 로드")

    if not notices:
        print("⚠️ notices 테이블에 데이터가 없습니다.")
        cursor.close()
        conn.close()
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )

    insert_cursor = conn.cursor()
    total_chunks = 0

    for notice in notices:
        full_text = f"""
제목: {notice.get('title') or ''}
카테고리: {notice.get('category') or ''}
작성일: {notice.get('published_at') or ''}
출처: {notice.get('url') or ''}

본문:
{notice.get('content') or ''}
""".strip()

        chunks = splitter.split_text(full_text)

        for idx, chunk in enumerate(chunks):
            content_hash = make_hash(
                "notice",
                notice["id"],
                notice["title"],
                chunk,
                idx
            )

            insert_cursor.execute(
                """
                INSERT INTO context_chunks
                (source_type, source_id, category, title, chunk_text, chunk_index, url, content_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    chunk_text = VALUES(chunk_text),
                    category = VALUES(category),
                    title = VALUES(title),
                    url = VALUES(url)
                """,
                (
                    "notice",
                    notice["id"],
                    notice.get("category"),
                    notice.get("title"),
                    chunk,
                    idx,
                    notice.get("url"),
                    content_hash
                )
            )

            total_chunks += 1

        conn.commit()
        print(f"✅ {notice['title'][:60]} → {len(chunks)} chunks")

    insert_cursor.close()
    cursor.close()
    conn.close()

    print(f"🎉 notices → context_chunks 완료: 총 {total_chunks}개 chunk 저장")


if __name__ == "__main__":
    main()
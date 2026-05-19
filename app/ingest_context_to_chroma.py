import os
import mysql.connector
import chromadb
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "db"),
    "user": os.getenv("MYSQL_USER", "douner"),
    "password": os.getenv("MYSQL_PASSWORD", "1234"),
    "database": os.getenv("MYSQL_DATABASE", "douner_ref"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
}


def main():
    print("🤖 임베딩 모델 로딩 중...")

    embedding_model = HuggingFaceEmbeddings(
        model_name="jhgan/ko-sroberta-multitask",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

    print("✅ 임베딩 모델 로딩 완료")

    print("🚀 ChromaDB 연결 중...")

    chroma_client = chromadb.HttpClient(
        host=os.getenv("CHROMA_HOST", "vector-db"),
        port=int(os.getenv("CHROMA_PORT", 8000)),
        tenant="default_tenant",
        database="default_database"
    )

    collection = chroma_client.get_or_create_collection(
        name="douner_collection"
    )

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            id,
            source_type,
            source_id,
            category,
            title,
            chunk_text,
            chunk_index,
            url
        FROM context_chunks
        WHERE chunk_text IS NOT NULL
          AND chunk_text != ''
    """)

    rows = cursor.fetchall()
    print(f"📦 context_chunks {len(rows)}개 로드")

    if not rows:
        print("⚠️ 저장할 chunk가 없습니다.")
        cursor.close()
        conn.close()
        return

    documents = []
    ids = []
    metadatas = []

    for row in rows:
        documents.append(row["chunk_text"])
        ids.append(f"context_{row['id']}")

        metadatas.append({
            "context_id": str(row["id"]),
            "source_type": row["source_type"] or "",
            "source_id": str(row["source_id"] or ""),
            "category": row["category"] or "",
            "title": row["title"] or "",
            "chunk_index": str(row["chunk_index"]),
            "url": row["url"] or ""
        })

    print("🔢 임베딩 생성 중...")
    embeddings = embedding_model.embed_documents(documents)
    print("✅ 임베딩 생성 완료")

    batch_size = 100

    for i in range(0, len(documents), batch_size):
        collection.upsert(
            ids=ids[i:i + batch_size],
            documents=documents[i:i + batch_size],
            embeddings=embeddings[i:i + batch_size],
            metadatas=metadatas[i:i + batch_size]
        )

        print(f"✅ {min(i + batch_size, len(documents))}/{len(documents)} 저장 완료")

    cursor.close()
    conn.close()

    print("🎉 context_chunks → ChromaDB 저장 완료")


if __name__ == "__main__":
    main()
import os
import mysql.connector
import chromadb
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

def run_integrated_pipeline():
    db_config = {
        'host': 'douner-db',        # ✅ 컨테이너 이름으로 (내부 통신)
        'user': os.getenv("MYSQL_USER", "douner"),
        'password': os.getenv("MYSQL_PASSWORD", "1234"),
        'database': os.getenv("MYSQL_DATABASE", "douner_ref"),
        'port': 3306                # ✅ 컨테이너 내부는 3306 (3307은 외부포트)
    }

    data_dir = "/data/all_data"

    # ✅ 임베딩 모델 초기화 (rag_service.py랑 동일하게)
    print("🤖 임베딩 모델 로딩 중...")
    embedding_model = HuggingFaceEmbeddings(
        model_name="jhgan/ko-sroberta-multitask",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    print("✅ 임베딩 모델 로딩 완료!")

    # ChromaDB 연결
    print("🚀 ChromaDB 연결 중...")
    chroma_client = chromadb.HttpClient(
        host='douner-vector-db',
        port=8000,
        tenant="default_tenant",
        database="default_database"
    )

    # ✅ 기존 컬렉션 초기화 후 재생성 (중복 방지)
    try:
        chroma_client.delete_collection("douner_collection")
        print("🗑️ 기존 컬렉션 초기화")
    except:
        pass
    collection = chroma_client.get_or_create_collection(name="douner_collection")

    # MySQL 연결
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        print("🔗 MySQL 연결 성공!")
    except Exception as e:
        print(f"❌ MySQL 연결 실패: {e}")
        return

    if not os.path.exists(data_dir):
        print(f"❌ 에러: {data_dir} 경로가 없음!")
        return

    files = [f for f in os.listdir(data_dir) if f.endswith(".pdf")]
    print(f"📂 PDF {len(files)}개 발견")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )

    all_chunks = []
    all_ids = []
    all_embeddings = []  # ✅ 임베딩 리스트 추가
    idx = 0

    for file_name in files:
        # 카테고리 분류
        if any(k in file_name for k in ["비자", "거주", "체류"]):
            category = "비자"
        elif any(k in file_name for k in ["학사", "졸업", "수강"]):
            category = "학사"
        elif "장학" in file_name:
            category = "장학"
        else:
            category = "일반"

        file_path = os.path.join(data_dir, file_name)
        print(f"📖 {file_name} 처리 중... (분류: {category})")

        loader = PyMuPDFLoader(file_path)
        pages = loader.load()
        full_content = "\n".join([p.page_content for p in pages]).strip()

        if not full_content:
            print(f"⚠️ {file_name} 내용 없음, 스킵")
            continue

        # MySQL 저장 (중복 방지)
        cursor.execute(
            "INSERT INTO documents (category, title, content) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE content=%s",
            (category, file_name, full_content, full_content)
        )

        # 청크 분리
        splits = text_splitter.split_text(full_content)
        print(f"   → {len(splits)}개 청크 생성")

        for chunk in splits:
            all_chunks.append(chunk)
            all_ids.append(f"{file_name}_{idx}")
            idx += 1

    conn.commit()
    print(f"✅ MySQL 저장 완료 ({len(files)}건)")

    # ✅ 임베딩 생성 후 ChromaDB 저장
    print(f"🔢 총 {len(all_chunks)}개 청크 임베딩 중...")
    all_embeddings = embedding_model.embed_documents(all_chunks)
    print("✅ 임베딩 완료!")

    # ✅ 배치로 저장 (한번에 너무 많으면 에러남)
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        collection.add(
            documents=all_chunks[i:i+batch_size],
            embeddings=all_embeddings[i:i+batch_size],
            ids=all_ids[i:i+batch_size]
        )
        print(f"   → {min(i+batch_size, len(all_chunks))}/{len(all_chunks)} 저장 완료")

    print(f"✅ ChromaDB 저장 완료! (총 {len(all_chunks)}개 청크)")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    run_integrated_pipeline()
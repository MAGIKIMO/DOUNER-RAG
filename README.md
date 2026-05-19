# 🎓 Douner AI - 유학생 AI 상담 서비스

> RAG(Retrieval-Augmented Generation) 기반 유학생 도우미 챗봇

<br>

## 📌 프로젝트 소개

**Douner AI**는 한국 유학생들이 겪는 비자, 학사, 장학금 등 다양한 어려움을 AI가 실시간으로 답변해주는 챗봇 서비스입니다.

학교 공식 문서(PDF)를 기반으로 정확한 정보를 제공하며, 한국어·영어·중국어·일본어 **다국어 응답**을 지원합니다.

### 주요 기능

- 💬 유학생 관련 질문 AI 자동 답변 (비자, 학사, 장학금 등)
- 🌏 다국어 지원 (한국어, 영어, 중국어, 일본어)
- 📄 학교 공식 PDF 문서 기반 RAG 응답
- ⚡ 실시간 스트리밍 답변

<br>

## 🏗️ 아키텍처 구조

```
사용자 (브라우저)
        │ HTTP :80
        ▼
┌─────────────────────────────────────────────────┐
│              Docker Network                      │
│                                                  │
│   ┌─────────────┐                                │
│   │    Nginx    │  ← 리버스 프록시               │
│   │    :80      │                                │
│   └──────┬──────┘                                │
│          │ /api/ 프록시                           │
│          ▼                                       │
│   ┌─────────────────────┐    ┌────────────────┐  │
│   │  FastAPI (RAG App)  │───▶│   Groq API     │  │
│   │  uvicorn · :8000    │    │  (LLaMA3 LLM)  │  │
│   └──────┬──────────────┘    └────────────────┘  │
│          │                                       │
│    ┌─────┴──────┐                                │
│    ▼            ▼                                │
│ ┌──────────┐ ┌────────┐                          │
│ │ ChromaDB │ │ MySQL  │                          │
│ │ 벡터 DB  │ │ :3307  │                          │
│ │ :8001    │ └────────┘                          │
│ └──────────┘                                     │
│                                                  │
│   ┌──────────────────────────────────────────┐   │
│   │  HuggingFace Embedding (ko-sroberta)     │   │
│   └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
        Ubuntu Server · 168.107.24.2
```

### RAG 처리 흐름

```
사용자 질문
    → ko-sroberta 임베딩 (벡터화)
    → ChromaDB 유사도 검색 (top-3 문서)
    → Groq LLaMA3 (질문 + 문서 → 답변 생성)
    → 사용자에게 응답
```

<br>

## 🛠️ 기술 스택

| 분류 | 기술 |
|------|------|
| **LLM** | Groq API (LLaMA 3.3 70B) |
| **Embedding** | jhgan/ko-sroberta-multitask |
| **Vector DB** | ChromaDB 1.5.5 |
| **Backend** | FastAPI + Uvicorn |
| **Database** | MySQL 8.0 |
| **Web Server** | Nginx |
| **Infra** | Docker, Docker Compose |
| **OS** | Ubuntu Server |
| **PDF 파싱** | PyMuPDF |
| **RAG Framework** | LangChain |

<br>

## ⚙️ 설치 및 실행 방법

### 사전 요구사항

- Docker, Docker Compose 설치
- Groq API Key 발급 ([console.groq.com](https://console.groq.com))

### 1. 저장소 클론

```bash
git clone https://github.com/your-repo/douner_project.git
cd douner_project
```

### 2. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일 수정:

```env
DB_HOST=douner-db
DB_USER=douner
DB_PASSWORD=your_password
DB_NAME=douner_ref
DB_PORT=3306

CHROMA_HOST=douner-vector-db
CHROMA_PORT=8000

GROQ_API_KEY=gsk_your_api_key
```

### 3. Docker 컨테이너 실행

```bash
sudo docker-compose up --build -d
```

### 4. MySQL DB 초기화

```bash
sudo docker-compose exec db mysql -u root -p
```

```sql
CREATE DATABASE douner_ref CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON douner_ref.* TO 'douner'@'%';
FLUSH PRIVILEGES;

USE douner_ref;
CREATE TABLE documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(50),
    title VARCHAR(255) UNIQUE,
    content LONGTEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5. PDF 문서 벡터화

`data/all_data/` 디렉토리에 PDF 파일 추가 후:

```bash
sudo docker-compose exec douner-rag-app python ingest.py
```

### 6. 서버 확인

```bash
# 서버 상태 확인
curl http://localhost:8000/api/v1/heartbeat

# API 테스트
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "비자 신청 방법 알려줘", "language": "ko"}'
```

### 7. 웹 접속

```
http://서버IP
```

<br>

## 📁 프로젝트 구조

```
douner_project/
├── app/
│   ├── chroma_db/          # ChromaDB 로컬 데이터
│   ├── database.py         # DB 연결 관리
│   ├── ingest.py           # PDF → 벡터화 파이프라인
│   ├── main.py             # FastAPI 엔트리포인트
│   ├── rag_service.py      # RAG 핵심 로직
│   └── requirements.txt    # Python 패키지
├── data/
│   ├── all_data/           # 원본 PDF 문서
│   ├── mysql_data/         # MySQL 데이터
│   └── vector_data/        # 벡터 데이터
├── html/
│   ├── chat.html           # 챗봇 UI
│   └── index.html          # 메인 페이지
├── .env                    # 환경변수 (git 제외)
├── docker-compose.yml      # Docker 설정
├── nginx.conf              # Nginx 설정
└── README.md
```

<br>

## 🚀 컨테이너 관리

```bash
# 전체 시작
sudo docker-compose up -d

# 전체 중지
sudo docker-compose down

# 로그 확인
sudo docker-compose logs -f douner-rag-app

# 특정 컨테이너 재시작
sudo docker-compose restart douner-rag-app

# 상태 확인
sudo docker-compose ps
```
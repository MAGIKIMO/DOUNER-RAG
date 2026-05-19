🎓 Douner AI - 동아대학교 RAG 기반 AI 상담 서비스
동아대학교 공지사항과 안내 문서를 기반으로 답변하는 RAG(Retrieval-Augmented Generation) AI 챗봇


📌 프로젝트 소개
Douner AI는 동아대학교 유학생 및 재학생이 학사, 유학생 지원, 인턴십, 비자, 생활 정보 등을 자연어로 질문할 수 있는 AI 상담 서비스입니다.

동아대학교 학사공지, 국제교류처 공지, 컴퓨터공학과 공지, PDF 안내문 데이터를 수집하고,
이를 기반으로 관련 문서를 검색한 뒤 Groq LLM을 통해 답변을 생성합니다.

단순 LLM 챗봇이 아니라,
크롤링 → MySQL 저장 → context chunk 관리 → ChromaDB 벡터 검색 → LLM 답변 생성 흐름을 갖는 RAG 서비스입니다.

주요 기능
💬 동아대학교 관련 질문 AI 자동 답변
📢 동아대학교 공지사항 크롤링
🌏 다국어 답변 지원: 한국어, 일본어, 영어, 중국어
📄 PDF 안내문 및 학교 공지 기반 RAG 검색
🔎 답변에 참고 자료 제목 및 URL 표시
👤 회원가입 / 로그인
📝 채팅 기록 저장
🐳 Docker Compose 기반 멀티 컨테이너 구성
🌐 Nginx Reverse Proxy 적용
접속 IP
http://34.64.196.94/ (도메인 구매 예정)

🏗️ 아키텍처 구조
사용자 브라우저
        │
        │ HTTP :80
        ▼
┌──────────────────────────────────────────────┐
│              Nginx                           │
│  - 정적 페이지 제공                           │
│  - /api/ 요청을 FastAPI로 프록시              │
└──────────────────┬───────────────────────────┘
                   │ Docker 내부 네트워크
                   ▼
┌──────────────────────────────────────────────┐
│              FastAPI                         │
│  - 로그인 / 회원가입 API                       │
│  - 질문 API                                   │
│  - RAGService 호출                            │
└───────┬───────────────────────┬──────────────┘
        │                       │
        ▼                       ▼
┌──────────────┐        ┌──────────────────┐
│   MySQL      │        │    ChromaDB      │
│              │        │                  │
│ users        │        │ Vector Search    │
│ chat_history │        │ Embedded Chunks  │
│ documents    │        └────────┬─────────┘
│ notices      │                 │
│ context_chunks│                │
└──────────────┘                 ▼
                          ┌──────────────┐
                          │  Groq LLM    │
                          │ Answer Gen.  │
                          └──────────────┘
RAG 처리 흐름
동아대학교 공지사항 / PDF 안내문
    ↓
crawler.py / ingest script
    ↓
MySQL notices / documents
    ↓
context_chunks 생성
    ↓
HuggingFace Embedding
    ↓
ChromaDB 저장
    ↓
사용자 질문 입력
    ↓
질문 Embedding
    ↓
ChromaDB 유사도 검색
    ↓
검색된 context + 질문을 Groq LLM에 전달
    ↓
답변 + 참고 자료 반환

🛠️ 기술 스택
분류	기술
LLM	Groq API / LLaMA 3.3 70B
Embedding	HuggingFace Embeddings / jhgan/ko-sroberta-multitask
Vector DB	ChromaDB
Backend	Python, FastAPI, Uvicorn
Database	MySQL 8.0
Web Server	Nginx
Infra	Docker, Docker Compose
Cloud / Server	GCP Compute Engine, Ubuntu Server
Crawling	requests, BeautifulSoup4
PDF Parsing	PyMuPDF
Text Splitting	LangChain Text Splitter
<br>
⚙️ 설치 및 실행 방법
사전 요구사항
Docker
Docker Compose
Groq API Key
1. 저장소 클론
git clone https://github.com/sanakang0/douner_project.git
cd douner_project
2. 환경변수 설정

루트 디렉토리에 .env 파일을 생성합니다.

MYSQL_DATABASE=douner_ref
MYSQL_ROOT_PASSWORD=your_root_password
MYSQL_USER=douner
MYSQL_PASSWORD=your_password

MYSQL_HOST=db
MYSQL_PORT=3306

CHROMA_HOST=vector-db
CHROMA_PORT=8000

GROQ_API_KEY=your_groq_api_key

.env 파일은 GitHub에 올리지 않습니다.

3. Docker 컨테이너 실행
sudo docker compose up -d --build
4. 컨테이너 상태 확인
sudo docker ps

정상 상태 예시:

douner-web          Up
douner-rag-app      Up
douner-db           Up
douner-vector-db    Up

외부 공개 포트는 Nginx의 80번만 사용합니다.

외부 사용자 → Nginx:80
Nginx → FastAPI:8000
FastAPI → MySQL:3306
FastAPI → ChromaDB:8000
5. 서버 상태 확인
curl http://localhost/api/v1/heartbeat

정상 응답 예시:

{
  "status": "alive",
  "connections": {
    "mysql": "Connected",
    "chromadb": "Connected",
    "rag_initialized": true
  }
}

6. MySQL 테이블 생성
sudo docker exec -it douner-db mysql -u douner -p douner_ref
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(255) UNIQUE,
    password VARCHAR(255),
    provider VARCHAR(50) DEFAULT 'local',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    question TEXT,
    answer LONGTEXT,
    language VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(50),
    title VARCHAR(255) UNIQUE,
    content LONGTEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    category VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    content LONGTEXT NOT NULL,
    url TEXT,
    published_at VARCHAR(50),
    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_hash VARCHAR(64) UNIQUE
);

CREATE TABLE IF NOT EXISTS context_chunks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    source_id INT,
    category VARCHAR(50),
    title VARCHAR(255),
    chunk_text LONGTEXT NOT NULL,
    chunk_index INT NOT NULL,
    url TEXT,
    content_hash VARCHAR(64) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

확인:

SHOW TABLES;
7. 공지사항 크롤링

동아대학교 학사공지, 국제교류처 공지, 컴퓨터공학과 공지 등을 수집합니다.

sudo docker exec -it douner-rag-app python -u crawler.py

DB 확인:

sudo docker exec -it douner-db mysql -u douner -p douner_ref
SELECT source, COUNT(*) FROM notices GROUP BY source;

SELECT id, source, category, title, url
FROM notices
ORDER BY id DESC
LIMIT 10;
8. 크롤링 데이터 RAG 반영
1) notices → context_chunks 변환
sudo docker exec -it douner-rag-app python -u ingest_notices_to_context.py
2) context_chunks → ChromaDB 저장
sudo docker exec -it douner-rag-app python -u ingest_context_to_chroma.py
3) RAG 서버 재시작
sudo docker restart douner-rag-app
9. API 테스트
한국어 질문
curl -X POST http://localhost/api/v1/ask \
-H "Content-Type: application/json" \
-d '{"question":"동아대학교 유학생 인턴십 공지 알려줘","language":"ko"}'
일본어 질문
curl -X POST http://localhost/api/v1/ask \
-H "Content-Type: application/json" \
-d '{"question":"東亜大学の留学生向けのお知らせを教えてください","language":"ja"}'

응답 예시:

{
  "question": "동아대학교 유학생 인턴십 공지 알려줘",
  "language": "ko",
  "answer": "동아대학교 유학생 인턴십 관련 공지로는 ...",
  "sources": [
    {
      "title": "공지 제목",
      "url": "공지 URL",
      "category": "유학생",
      "source_type": "notice"
    }
  ],
  "debug_info": {
    "retrieved_context": "..."
  }
}
10. 웹 접속

브라우저에서 아래 주소로 접속합니다.

http://서버IP

로컬 테스트:

http://localhost
📁 프로젝트 구조
douner_project/
├── app/
│   ├── crawler.py                      # 동아대학교 공지사항 크롤링
│   ├── database.py                     # DB 연결 확인
│   ├── ingest_notices_to_context.py    # notices → context_chunks 변환
│   ├── ingest_context_to_chroma.py      # context_chunks → ChromaDB 저장
│   ├── legacy_pdf_ingest.py             # 기존 PDF ingest 백업
│   ├── main.py                         # FastAPI 엔트리포인트
│   ├── rag_service.py                  # RAG 핵심 로직
│   └── requirements.txt
│
├── data/
│   ├── all_data/                       # 원본 PDF 문서, git 제외
│   ├── mysql_data/                     # MySQL 데이터, git 제외
│   └── vector_data/                    # ChromaDB 데이터, git 제외
│
├── html/
│   ├── chat.html
│   ├── login.html
│   ├── signup.html
│   └── mypage.html
│
├── docker-compose.yml
├── nginx.conf
├── .env                                # git 제외
├── .gitignore
└── README.md

주요 스크립트 설명
crawler.py

동아대학교 공지사항을 크롤링하여 notices 테이블에 저장합니다.

현재 크롤링 대상:

동아대학교 학사공지
동아대학교 국제교류처 공지
동아대학교 컴퓨터공학과 공지
동아대학교 컴퓨터공학과 취업정보
동아대학교 컴퓨터공학과 대회정보
동아대학교 컴퓨터공학과 교육정보

ingest_notices_to_context.py

notices 테이블의 원문 데이터를 RAG 검색 단위인 context_chunks로 분할합니다.

ingest_context_to_chroma.py

context_chunks의 chunk_text를 embedding하고 ChromaDB에 저장합니다.

rag_service.py

사용자 질문을 embedding하고 ChromaDB에서 유사 문서를 검색한 뒤,
검색된 context를 Groq LLM에 전달하여 답변을 생성합니다.

응답에는 참고 자료 정보도 포함됩니다.

컨테이너 관리
# 전체 시작
sudo docker compose up -d

# 전체 중지
sudo docker compose down

# 로그 확인
sudo docker logs douner-rag-app --tail 100

# 특정 컨테이너 재시작
sudo docker restart douner-rag-app

# 상태 확인
sudo docker ps
문제 해결
douner-rag-app이 실행되지 않을 때
sudo docker logs douner-rag-app --tail 100
RAG 서비스가 준비되지 않았다고 나올 때
curl http://localhost/api/v1/heartbeat

rag_initialized가 false라면 아래 항목을 확인합니다.

.env에 GROQ_API_KEY가 있는지
ChromaDB 컨테이너가 실행 중인지
douner_collection이 생성되었는지
rag_service.py에서 get_or_create_collection()을 사용하는지
ChromaDB에 데이터 다시 넣기
sudo docker exec -it douner-rag-app python -u ingest_context_to_chroma.py
sudo docker restart douner-rag-app
Docker 빌드 중 용량 부족

AI 관련 라이브러리 설치 중 아래 에러가 발생할 수 있습니다.

OSError: [Errno 28] No space left on device

확인:

df -h
lsblk
sudo docker system df

Docker 캐시 정리:

sudo docker builder prune -a
sudo docker image prune -a

GCP 디스크 확장 후 root partition 확장:

sudo growpart /dev/sda 1
sudo resize2fs /dev/sda1

주의:

sudo docker system prune -a --volumes

위 명령어는 MySQL / ChromaDB volume 데이터가 삭제될 수 있으므로 주의해야 합니다.

GitHub에 올리면 안 되는 파일

아래 파일과 폴더는 GitHub에 올리지 않습니다.

.env
data/mysql_data/
data/vector_data/
data/all_data/
__pycache__/
*.pyc

.gitignore 예시:

.env
__pycache__/
*.pyc

data/mysql_data/
data/vector_data/
data/all_data/

.vscode/
.idea/
.DS_Store
get-docker.sh
prometheus.yml
팀원 작업 가이드
프론트엔드 담당
html/chat.html
html/login.html
html/signup.html
html/mypage.html

작업 내용:

채팅 UI 개선
로그인 / 회원가입 UI 개선
참고 자료 sources 표시 디자인 개선
모바일 화면 대응
백엔드 담당
app/main.py

작업 내용:

로그인 API
회원가입 API
질문 API
채팅 기록 저장
API 에러 처리 개선
RAG / 데이터 담당
app/crawler.py
app/ingest_notices_to_context.py
app/ingest_context_to_chroma.py
app/rag_service.py

작업 내용:

크롤링 대상 추가
공지사항 본문 정제
context_chunks 구조 관리
ChromaDB 저장
Groq prompt 개선
인프라 담당
docker-compose.yml
nginx.conf
.env
GCP 서버

작업 내용:

Docker Compose 관리
Nginx Reverse Proxy 설정
포트 공개 제한
서버 용량 관리
GCP 방화벽 설정
현재 구현 상태
Docker Compose 기반 서비스 실행
Nginx Reverse Proxy
FastAPI API 서버
MySQL 사용자 / 공지 / 대화 기록 저장
ChromaDB vector search
Groq LLM 응답 생성
동아대학교 국제교류처 공지 크롤링
동아대학교 학사공지 크롤링
동아대학교 컴퓨터공학과 공지 크롤링
context_chunks 기반 RAG 데이터 관리
RAG 답변 출처 표시
향후 개선 예정
LMS 로그인 기반 크롤링
공지사항 본문 정제 고도화
PDF 첨부파일 자동 다운로드 및 ingest
Prometheus / Grafana 모니터링
CI/CD 자동 배포
Terraform 기반 인프라 코드화
Kubernetes 확장
답변 품질 개선
출처 표시 UI 개선
Monica
Monica
저장소 요약
가장 진보된 모델을 지원하여 저장소 내용을 빠르게 이해할 수 있도록 도와줍니다
About
RAG 기반 유학생 생활·행정 절차 안내 AI 서비스 개발

Resources
 Readme
 Activity
Stars
 0 stars
Watchers
 0 watching
Forks
 0 forks
Releases
No releases published
Create a new release
Packages
No packages published
Publish your first package
Contributors
3
@MAGIKIMO
MAGIKIMO
@sanakang0
sanakang0 Haram Kang
@gwonnamgyu
gwonnamgyu
Languages
HTML
69.0%
 
Python
30.8%
 
Dockerfile
0.2%

Footer navigation
Terms
P

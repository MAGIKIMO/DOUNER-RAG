from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
import logging
from database import check_mysql_connection, check_chromadb_connection
from rag_service import RAGService
import mysql.connector
from mysql.connector import Error as MySQLError
import hashlib
import os
from fastapi import Header
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DounerAI")

app = FastAPI(title="Douner AI Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    language: str = "ko"


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str
    rememberMe: bool = False


rag = None


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", os.getenv("DB_HOST", "douner-db")),
        user=os.getenv("MYSQL_USER", os.getenv("DB_USER", "douner")),
        password=os.getenv("MYSQL_PASSWORD", os.getenv("DB_PASSWORD", "1234")),
        database=os.getenv("MYSQL_DATABASE", os.getenv("DB_NAME", "douner_ref")),
        port=int(os.getenv("MYSQL_PORT", os.getenv("DB_PORT", 3306)))
    )


def ensure_auth_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            provider VARCHAR(30) DEFAULT 'local',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            question TEXT NOT NULL,
            answer LONGTEXT NOT NULL,
            language VARCHAR(10) DEFAULT 'ko',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_chat_history_user_created (user_id, created_at),
            CONSTRAINT fk_chat_history_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """)

    conn.commit()
    cursor.close()
    conn.close()


def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()


def token_for_user(user):
    return hashlib.sha256(f"{user['id']}{user['email']}".encode()).hexdigest()


def get_bearer_token(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.split(" ", 1)[1].strip()


def get_user_by_token(token: Optional[str]):
    if not token:
        return None

    ensure_auth_tables()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, provider, created_at FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()

    for user in users:
        if token_for_user(user) == token:
            return user

    return None


@app.on_event("startup")
async def startup_event():
    global rag
    try:
        ensure_auth_tables()
        logger.info("✅ Auth tables 준비 완료")
    except Exception as e:
        logger.error(f"❌ Auth tables 초기화 실패: {str(e)}")

    try:
        rag = RAGService()
        logger.info("🚀 RAG Service 가동 준비 완료!")
    except Exception as e:
        logger.error(f"❌ RAG 서비스 초기화 실패: {str(e)}")


@app.get("/api/v1/heartbeat")
def check_connectivity():
    return {
        "status": "alive",
        "connections": {
            "mysql": check_mysql_connection(),
            "chromadb": check_chromadb_connection(),
            "rag_initialized": rag is not None
        }
    }


@app.post("/api/v1/ask")
async def ask_question(req: AskRequest, authorization: Optional[str] = Header(None)):
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG 서비스가 준비되지 않았습니다.")

    try:
        answer, source_text, sources = await run_in_threadpool(
            rag.get_answer,
            req.question,
            req.language
        )

        token = get_bearer_token(authorization)
        if token:
            try:
                user = get_user_by_token(token)
                if user:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO chat_history (user_id, question, answer, language) VALUES (%s, %s, %s, %s)",
                        (user["id"], req.question, answer, req.language)
                    )
                    conn.commit()
                    cursor.close()
                    conn.close()
            except Exception as e:
                logger.error(f"대화기록 저장 실패: {e}")

        return {
            "question": req.question,
            "language": req.language,
            "answer": answer,
            "sources": sources,
            "debug_info": {
                "retrieved_context": source_text
            }
        }
    except Exception as e:
        logger.error(f"Error during RAG execution: {e}")
        raise HTTPException(status_code=500, detail=f"답변 생성 중 오류 발생: {str(e)}")


@app.post("/api/v1/signup")
async def signup(req: SignupRequest):
    if not req.name.strip() or not req.email.strip() or not req.password:
        raise HTTPException(status_code=400, detail="이름, 이메일, 비밀번호를 모두 입력해주세요.")

    try:
        ensure_auth_tables()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password, provider) VALUES (%s, %s, %s, 'local')",
            (req.name.strip(), req.email.strip(), hash_password(req.password))
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "회원가입 성공"}
    except MySQLError as e:
        if e.errno == 1062:
            raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/login")
async def login(req: LoginRequest):
    try:
        ensure_auth_tables()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        hashed_pw = hash_password(req.password)
        cursor.execute(
            "SELECT * FROM users WHERE email = %s AND password = %s",
            (req.email.strip(), hashed_pw)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 틀렸습니다.")

        token = token_for_user(user)

        return {
            "message": "로그인 성공",
            "token": token,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/me")
async def me(authorization: Optional[str] = Header(None)):
    user = get_user_by_token(get_bearer_token(authorization))

    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    return {
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "provider": user.get("provider", "local"),
            "created_at": str(user.get("created_at", ""))
        }
    }


@app.get("/api/v1/chat-history")
async def get_chat_history(authorization: Optional[str] = Header(None), limit: int = 50):
    user = get_user_by_token(get_bearer_token(authorization))

    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    limit = min(max(limit, 1), 100)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, question, answer, language, created_at
        FROM chat_history
        WHERE user_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT %s
        """,
        (user["id"], limit)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    rows.reverse()

    return {
        "user_id": user["id"],
        "history": [
            {
                "id": row["id"],
                "question": row["question"],
                "answer": row["answer"],
                "language": row["language"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None
            }
            for row in rows
        ]
    }


@app.delete("/api/v1/chat-history")
async def delete_chat_history(authorization: Optional[str] = Header(None)):
    user = get_user_by_token(get_bearer_token(authorization))

    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE user_id = %s", (user["id"],))
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "대화 기록이 삭제되었습니다.", "deleted": deleted}

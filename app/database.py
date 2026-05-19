import os
import mysql.connector
import requests
from dotenv import load_dotenv

load_dotenv()

def check_mysql_connection():
    try:
        db = mysql.connector.connect(
            host=os.getenv("DB_HOST", "douner-db"),        # ✅ 컨테이너명
            user=os.getenv("DB_USER", "douner"),            # ✅ 기본값 수정
            password=os.getenv("DB_PASSWORD", "1234"),      # ✅ 기본값 추가
            database=os.getenv("DB_NAME", "douner_ref"),    # ✅ douner_ref로 수정
            port=int(os.getenv("DB_PORT", 3306)),           # ✅ 내부포트 3306
            auth_plugin='mysql_native_password'
        )
        db.close()
        return "✅ Connected"
    except Exception as e:
        return f"❌ Failed: {str(e)}"

def check_chromadb_connection():
    try:
        response = requests.get("http://douner-vector-db:8000/api/v2/heartbeat", timeout=3)
        if response.status_code == 200:
            return "✅ Connected (v2)"
        return f"⚠️ Status: {response.status_code}"
    except Exception as e:
        return f"❌ Failed: {str(e)}"
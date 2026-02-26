import os
import time
from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "appdb")
DB_USER = os.getenv("DB_USER", "app")
DB_PASS = os.getenv("DB_PASS", "apppw")

def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )

@app.get("/healthz")
def healthz():
    return "ok", 200

@app.get("/api/ping")
def ping():
    # DB까지 왕복 쿼리로 “WAS->DB 통신”을 확실히 검증
    for _ in range(3):
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT now();")
                    now = cur.fetchone()[0].isoformat()
            return jsonify({"status": "ok", "db_time": now}), 200
        except Exception as e:
            last = str(e)
            time.sleep(1)
    return jsonify({"status": "error", "error": last}), 500

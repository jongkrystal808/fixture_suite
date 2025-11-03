import os
import io
import csv
import hashlib
from typing import Optional, List, Any, Dict

import pandas as pd
import pymysql
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import time


# ---------- Config ----------
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "fixture_management")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "Chch1014")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_ROOT = os.path.join(APP_DIR, "web")
UPLOAD_DIR = os.path.join(APP_DIR, "uploads")
os.makedirs(WEB_ROOT, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 🧩 啟動時印出環境變數（除密碼外）
print("====== [DB CONFIG LOADED] ======")
print(f"DB_HOST = {DB_HOST}")
print(f"DB_PORT = {DB_PORT}")
print(f"DB_NAME = {DB_NAME}")
print(f"DB_USER = {DB_USER}")
print(f"DB_PASS (masked) = {'*' * len(DB_PASS)}")
print("================================")



# ---------- App ----------
app = FastAPI(title="Fixture Management API", version="5.0.0")
@app.get("/")
def root():
    return JSONResponse({"message": "API is running", "db_host": DB_HOST})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/app", StaticFiles(directory=WEB_ROOT, html=True), name="app")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/app/index.html")



# ---------- DB ----------
def get_db():
    """連線到 MySQL（若未啟動則重試 10 次，每次間隔 2 秒）"""
    import time
    for i in range(10):
        try:
            conn = pymysql.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASS,
                database=DB_NAME,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
            )
            if i > 0:
                print(f"✅ 已成功連線 MySQL（第 {i+1} 次嘗試）")
            return conn
        except Exception as e:
            print(f"⚠️ 第 {i+1}/10 次連線 MySQL 失敗：{e}")
            time.sleep(2)
    raise Exception("❌ 無法連線到 MySQL，請確認容器是否正常啟動")

def hash_password(pw: str) -> str:
    return hashlib.sha256((pw or "").encode("utf-8")).hexdigest()

def init_tables():
    conn = get_db()
    c = conn.cursor()

    # users
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE,
            password_hash VARCHAR(255),
            role VARCHAR(20)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # fixtures (治具)
    c.execute("""
        CREATE TABLE IF NOT EXISTS fixtures (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255),
            status VARCHAR(50),
            life_type VARCHAR(50),
            used INT DEFAULT 0,
            life_value INT DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # fixture_models (治具資料維護)
    c.execute("""
        CREATE TABLE IF NOT EXISTS fixture_models (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(100),
            name VARCHAR(255),
            spec VARCHAR(255),
            note VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # fixture_requirements (機種與治具需求關聯)
    c.execute("""
              CREATE TABLE IF NOT EXISTS fixture_requirements
              (
                  id
                  INT
                  AUTO_INCREMENT
                  PRIMARY
                  KEY,
                  model_code
                  VARCHAR
              (
                  100
              ),
                  station VARCHAR
              (
                  100
              ),
                  fixture_code VARCHAR
              (
                  100
              ),
                  required_qty INT DEFAULT 0
                  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
              """)

    # machine_models (機種資料維護)
    c.execute("""
        CREATE TABLE IF NOT EXISTS machine_models (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(100),
            name VARCHAR(255),
            note VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # receipts (收料)
    c.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            type VARCHAR(20),
            vendor VARCHAR(255),
            order_no VARCHAR(255),
            fixture_code VARCHAR(255),
            serial_start VARCHAR(255),
            serial_end VARCHAR(255),
            serials TEXT,
            operator VARCHAR(255),
            note VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # returns (退料)
    c.execute("""
        CREATE TABLE IF NOT EXISTS returns_table (
            id INT AUTO_INCREMENT PRIMARY KEY,
            type VARCHAR(20),
            vendor VARCHAR(255),
            order_no VARCHAR(255),
            fixture_code VARCHAR(255),
            serial_start VARCHAR(255),
            serial_end VARCHAR(255),
            serials TEXT,
            operator VARCHAR(255),
            note VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # logs (使用/更換記錄)
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            fixture VARCHAR(255),
            type VARCHAR(50),
            note VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # settings (包含 smtp 設定)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category VARCHAR(50),
            skey VARCHAR(100),
            svalue TEXT,
            UNIQUE KEY uniq_k (category, skey)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # default admin
    c.execute("SELECT COUNT(*) AS n FROM users WHERE username=%s", ("admin",))
    row = c.fetchone()
    if (row or {}).get("n", 0) == 0:
        c.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s,%s,%s)",
            ("admin", hash_password("admin"), "admin"),
        )

    conn.commit()
    conn.close()

# 啟動時自動建立資料表
try:
    init_tables()
    print("✅ 資料表初始化完成")
except Exception as e:
    print("⚠️ 初始化資料表失敗:", e)


# ---------- Schemas ----------
class PageResp(BaseModel):
    total: int
    page: int
    page_size: int
    data: List[Dict[str, Any]]

class UserIn(BaseModel):
    username: str
    password: Optional[str] = None
    role: str = Field(default="user", pattern="^(admin|user)$")

class FixtureIn(BaseModel):
    name: str
    status: str = "active"
    life_type: str = "count"
    used: int = 0
    life_value: int = 0

class ReceiptIn(BaseModel):
    type: str = Field(default="batch")
    vendor: str = Field(default="")
    order_no: str = Field(default="")
    fixture_code: str = Field(default="")
    serial_start: str = Field(default="")
    serial_end: str = Field(default="")
    serials: str = Field(default="")
    operator: str = Field(default="")
    note: Optional[str] = None

class ReturnIn(BaseModel):
    type: str = Field(default="batch")
    vendor: str = Field(default="")
    order_no: str = Field(default="")
    fixture_code: str = Field(default="")
    serial_start: str = Field(default="")
    serial_end: str = Field(default="")
    serials: str = Field(default="")
    operator: str = Field(default="")
    note: Optional[str] = None

class LogIn(BaseModel):
    fixture: str
    type: str
    note: Optional[str] = None

# ---------- Auth ----------
@app.post("/login")
def login(body: UserIn):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=%s", (body.username,))
    row = c.fetchone()
    conn.close()
    if not row: raise HTTPException(status_code=401, detail="帳號不存在")
    if hash_password(body.password or "") != row["password_hash"]:
        raise HTTPException(status_code=401, detail="密碼錯誤")
    return {"username": row["username"], "role": row["role"]}

# ---------- Users ----------
@app.get("/users", response_model=PageResp)
def list_users(q: Optional[str] = None, page: int = 1, page_size: int = 20):
    conn = get_db(); c = conn.cursor()
    base = "FROM users WHERE 1=1"
    params = []
    if q:
        base += " AND (username LIKE %s OR role LIKE %s)"
        like = f"%{q}%"; params += [like, like]
    c.execute(f"SELECT COUNT(*) AS total {base}", params); total = (c.fetchone() or {}).get("total", 0)
    off = (page-1)*page_size
    c.execute(f"SELECT username, role {base} ORDER BY username LIMIT %s OFFSET %s", params + [page_size, off])
    data = c.fetchall() or []
    conn.close()
    return PageResp(total=total, page=page, page_size=page_size, data=data)

@app.post("/users")
def create_user(body: UserIn):
    conn = get_db(); c = conn.cursor()
    try:
        pw = hash_password(body.password or "1234")
        c.execute("INSERT INTO users (username, password_hash, role) VALUES (%s,%s,%s)", (body.username, pw, body.role))
        conn.commit()
    except Exception as e:
        conn.rollback(); raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
    return {"ok": True}

@app.put("/users/{username}")
def update_user(username: str, body: UserIn):
    conn = get_db(); c = conn.cursor()
    updates = []; params = []
    if body.password:
        updates.append("password_hash=%s"); params.append(hash_password(body.password))
    if body.role:
        updates.append("role=%s"); params.append(body.role)
    if not updates: raise HTTPException(status_code=400, detail="No updates provided")
    params.append(username)
    c.execute(f"UPDATE users SET {', '.join(updates)} WHERE username=%s", params)
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/users/{username}")
def delete_user(username: str):
    if username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete default admin")
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM users WHERE username=%s", (username,))
    conn.commit(); conn.close()
    return {"ok": True}

# ---------- Fixtures (治具) ----------
@app.get("/fixtures")
def get_fixtures(q: Optional[str] = None):
    conn = get_db(); c = conn.cursor()
    if q:
        like = f"%{q}%"
        c.execute("SELECT * FROM fixtures WHERE name LIKE %s OR status LIKE %s ORDER BY id DESC", (like, like))
    else:
        c.execute("SELECT * FROM fixtures ORDER BY id DESC")
    rows = c.fetchall() or []; conn.close(); return rows

@app.post("/fixtures")
def create_fixture(body: FixtureIn):
    conn = get_db(); c = conn.cursor()
    c.execute("""INSERT INTO fixtures (name, status, life_type, used, life_value) VALUES (%s,%s,%s,%s,%s)""",
        (body.name, body.status, body.life_type, body.used, body.life_value))
    conn.commit(); conn.close(); return {"ok": True}

@app.put("/fixtures/{fid}")
def update_fixture(fid: int, body: FixtureIn):
    conn = get_db(); c = conn.cursor()
    c.execute("""UPDATE fixtures SET name=%s, status=%s, life_type=%s, used=%s, life_value=%s WHERE id=%s""",
        (body.name, body.status, body.life_type, body.used, body.life_value, fid))
    conn.commit(); conn.close(); return {"ok": True}

@app.delete("/fixtures/{fid}")
def delete_fixture(fid: int):
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM fixtures WHERE id=%s", (fid,))
    conn.commit(); conn.close(); return {"ok": True}

# ---------- Fixture Models (治具資料維護) ----------
@app.get("/fixtures/models")
def list_fixture_models():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM fixture_models ORDER BY id DESC")
    rows = c.fetchall() or []; conn.close(); return rows

@app.post("/fixtures/models")
def add_fixture_model(code: str = Form(...), name: str = Form(...), spec: str = Form(""), note: str = Form("")):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO fixture_models (code, name, spec, note) VALUES (%s,%s,%s,%s)", (code, name, spec, note))
    conn.commit(); conn.close(); return {"ok": True}

@app.post("/fixtures/import_xlsx")
async def import_fixtures_xlsx(file: UploadFile = File(...)):
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))
    # 允許欄位：code,name,spec,note
    cols = {c.lower(): c for c in df.columns}
    need = ["code","name"]
    for k in need:
        if k not in cols:
            raise HTTPException(status_code=400, detail=f"缺少必要欄位：{k}")
    conn = get_db(); c = conn.cursor()
    for _, row in df.iterrows():
        code = str(row.get(cols.get("code"), "")).strip()
        name = str(row.get(cols.get("name"), "")).strip()
        spec = str(row.get(cols.get("spec"), "")).strip() if "spec" in cols else ""
        note = str(row.get(cols.get("note"), "")).strip() if "note" in cols else ""
        if code and name:
            c.execute("INSERT INTO fixture_models (code, name, spec, note) VALUES (%s,%s,%s,%s)", (code,name,spec,note))
    conn.commit(); conn.close()
    return {"ok": True}

# ---------- Machine Models (機種資料維護) ----------
@app.get("/machines/models")
def list_machine_models():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM machine_models ORDER BY id DESC")
    rows = c.fetchall() or []; conn.close(); return rows

@app.post("/machines/models")
def add_machine_model(code: str = Form(...), name: str = Form(...), note: str = Form("")):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO machine_models (code, name, note) VALUES (%s,%s,%s)", (code, name, note))
    conn.commit(); conn.close(); return {"ok": True}

@app.post("/machines/import_xlsx")
async def import_machines_xlsx(file: UploadFile = File(...)):
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))
    cols = {c.lower(): c for c in df.columns}
    need = ["code","name"]
    for k in need:
        if k not in cols:
            raise HTTPException(status_code=400, detail=f"缺少必要欄位：{k}")
    conn = get_db(); c = conn.cursor()
    for _, row in df.iterrows():
        code = str(row.get(cols.get("code"), "")).strip()
        name = str(row.get(cols.get("name"), "")).strip()
        note = str(row.get(cols.get("note"), "")).strip() if "note" in cols else ""
        if code and name:
            c.execute("INSERT INTO machine_models (code, name, note) VALUES (%s,%s,%s)", (code,name,note))
    conn.commit(); conn.close()
    return {"ok": True}

# ---------- Receipts / Returns ----------
@app.get("/receipts")
def list_receipts():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM receipts ORDER BY id DESC")
    rows = c.fetchall() or []; conn.close(); return rows

@app.post("/receipts")
def add_receipt(body: ReceiptIn):
    conn = get_db(); c = conn.cursor()
    c.execute("""INSERT INTO receipts (type, vendor, order_no, fixture_code, serial_start, serial_end, serials, operator, note) 
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
              (body.type, body.vendor, body.order_no, body.fixture_code, body.serial_start, body.serial_end, body.serials, body.operator, body.note))
    conn.commit(); conn.close(); return {"ok": True}

@app.delete("/receipts/{rid}")
def del_receipt(rid: int):
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM receipts WHERE id=%s", (rid,))
    conn.commit(); conn.close(); return {"ok": True}

@app.get("/returns")
def list_returns():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM returns_table ORDER BY id DESC")
    rows = c.fetchall() or []; conn.close(); return rows

@app.post("/returns")
def add_return(body: ReturnIn):
    conn = get_db(); c = conn.cursor()
    c.execute("""INSERT INTO returns_table (type, vendor, order_no, fixture_code, serial_start, serial_end, serials, operator, note) 
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
              (body.type, body.vendor, body.order_no, body.fixture_code, body.serial_start, body.serial_end, body.serials, body.operator, body.note))
    conn.commit(); conn.close(); return {"ok": True}

@app.delete("/returns/{rid}")
def del_return(rid: int):
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM returns_table WHERE id=%s", (rid,))
    conn.commit(); conn.close(); return {"ok": True}

# ---------- Logs ----------
@app.get("/logs")
def list_logs():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM logs ORDER BY id DESC")
    rows = c.fetchall() or []; conn.close(); return rows

@app.post("/logs")
def add_log(body: LogIn):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO logs (fixture, type, note) VALUES (%s,%s,%s)", (body.fixture, body.type, body.note))
    conn.commit(); conn.close(); return {"ok": True}

@app.get("/logs/export")
def export_logs():
    # Export CSV with UTF-8 BOM to avoid garbled characters when opened in Excel
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT created_at, fixture, type, note FROM logs ORDER BY id DESC")
    rows = c.fetchall() or []; conn.close()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["時間","治具","類型","備註"])
    for r in rows:
        writer.writerow([str(r.get("created_at") or ""), r.get("fixture") or "", r.get("type") or "", r.get("note") or ""])

    data = ("\ufeff" + buf.getvalue()).encode("utf-8")  # add BOM
    return StreamingResponse(io.BytesIO(data), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=logs.csv"})

# ---------- SMTP Settings ----------
@app.get("/settings/smtp")
def get_smtp_settings():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT skey, svalue FROM settings WHERE category='smtp'")
    rows = c.fetchall() or []; conn.close()
    out = {r["skey"]: r["svalue"] for r in rows}
    return out

@app.post("/settings/smtp")
def save_smtp_settings(
    host: str = Form(...),
    port: int = Form(...),
    user: str = Form(...),
    password: str = Form(...),
    sender: str = Form(...),
):
    conn = get_db(); c = conn.cursor()
    pairs = {"host":host, "port":str(port), "user":user, "pass":password, "sender":sender}
    for k,v in pairs.items():
        c.execute("""INSERT INTO settings (category, skey, svalue) VALUES ('smtp', %s, %s)
                     ON DUPLICATE KEY UPDATE svalue=VALUES(svalue)""", (k, v))
    conn.commit(); conn.close()
    return {"ok": True}

# ---------- Stats ----------
@app.get("/stats/summary")
def stats_summary():
    conn = get_db(); c = conn.cursor()
    def one(sql: str, params: tuple = ()):
        c.execute(sql, params); row = c.fetchone() or {}; return int(list(row.values())[0]) if row else 0
    try:
        total = one("SELECT COUNT(*) AS n FROM fixtures")
        active = one("SELECT COUNT(*) AS n FROM fixtures WHERE status='active'")
        under = one("SELECT COUNT(*) AS n FROM fixtures WHERE life_type='count' AND used < life_value")
        need = one("SELECT COUNT(*) AS n FROM fixtures WHERE life_type='count' AND used >= life_value")
    except Exception:
        init_tables(); total=active=under=need=0
    finally:
        conn.close()
    return {"total_fixtures": total, "active_fixtures": active, "under_lifespan": under, "need_replacement": need}

@app.get("/models/max_stations")
def get_max_stations(model_code: str):
    """
    計算指定機種在各站可開的最大站數
    """
    conn = get_db(); c = conn.cursor()

    # 查詢該機種各站治具需求
    c.execute("""
        SELECT station, fixture_code, required_qty
        FROM fixture_requirements
        WHERE model_code=%s
    """, (model_code,))
    reqs = c.fetchall()

    if not reqs:
        conn.close()
        raise HTTPException(status_code=404, detail=f"找不到機種 {model_code} 的需求資料")

    # 查庫存
    c.execute("SELECT name AS fixture_code, life_value AS stock_qty FROM fixtures")
    stock = {r["fixture_code"]: r["stock_qty"] for r in c.fetchall()}

    conn.close()

    # 計算
    station_avail = {}
    for r in reqs:
        f = r["fixture_code"]
        s = r["station"]
        need = r["required_qty"] or 0
        have = stock.get(f, 0)
        possible = have // need if need else 0
        station_avail.setdefault(s, []).append(possible)

    result = {s: min(v) if v else 0 for s, v in station_avail.items()}
    return {"model": model_code, "stations": result}
# Fixture Suite (FastAPI + MySQL + SPA)

## 啟動
```bash
docker compose up -d --build
```

- API: http://localhost:8000
- 前端: http://localhost:8000/app/index.html
- MySQL: 127.0.0.1:3307  （容器內為 3306）

## 預設帳號
- 帳號：admin
- 密碼：admin

## 匯入格式
- 治具資料維護 `fixtures/import_xlsx`：必需欄位 `code`, `name`；可選 `spec`, `note`
- 機種資料維護 `machines/import_xlsx`：必需欄位 `code`, `name`；可選 `note`

## 匯出
- 使用/更換記錄：`GET /logs/export` 下載 CSV（UTF-8 BOM，Excel 不會亂碼）

## 目錄
- `web/index.html`：單頁前端
- `main.py`：FastAPI 後端，MySQL 連線（環境變數見 docker-compose.yml）
- `uploads/`：檔案上傳位置
```


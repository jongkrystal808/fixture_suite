#!/bin/bash
echo "[BACKUP] Starting manual MySQL backup..."

# 時間戳記
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

# 備份輸出目錄（確保 /backup 存在）
BACKUP_DIR="/backup"
mkdir -p "$BACKUP_DIR"

# 檔案名稱
BACKUP_FILE="${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql"

# 執行備份
mysqldump -h fixture_mysql -u root -p"${DB_PASS}" "${DB_NAME}" > "$BACKUP_FILE"

# 壓縮備份（可選）
# zip "${BACKUP_FILE}.zip" "$BACKUP_FILE" && rm "$BACKUP_FILE"

echo "[BACKUP] Done: ${BACKUP_FILE}"

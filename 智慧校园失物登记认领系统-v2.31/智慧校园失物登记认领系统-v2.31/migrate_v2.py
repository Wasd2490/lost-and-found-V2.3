# -*- coding: utf-8 -*-
"""
v2 优化模块数据库迁移脚本（幂等可重复执行）
- users.trust_score
- lost_items / found_items: phash
- found_items.qa_json（发布招领时设置的密保问题）
- claim_records.answers_json / auto_passed
- sessions 表（会话持久化）
- notifications 表（轮询通知）
- 复合索引与普通索引
"""
import mysql.connector
from mysql.connector import Error

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "wan1314xy",
    "database": "lost_and_found",
    "charset": "utf8mb4",
}


def column_exists(cur, table, column):
    cur.execute(
        """SELECT COUNT(*) FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s""",
        (DB_CONFIG["database"], table, column),
    )
    return cur.fetchone()[0] > 0


def table_exists(cur, table):
    cur.execute(
        """SELECT COUNT(*) FROM information_schema.TABLES
           WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s""",
        (DB_CONFIG["database"], table),
    )
    return cur.fetchone()[0] > 0


def index_exists(cur, table, index_name):
    cur.execute(
        """SELECT COUNT(*) FROM information_schema.STATISTICS
           WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND INDEX_NAME=%s""",
        (DB_CONFIG["database"], table, index_name),
    )
    return cur.fetchone()[0] > 0


def add_column(cur, table, column, ddl):
    if column_exists(cur, table, column):
        print("  [skip] %s.%s 已存在" % (table, column))
    else:
        cur.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, ddl))
        print("  [ok]   %s.%s 已添加" % (table, column))


def add_index(cur, table, index_name, ddl):
    if index_exists(cur, table, index_name):
        print("  [skip] 索引 %s.%s 已存在" % (table, index_name))
    else:
        cur.execute("CREATE INDEX %s ON %s %s" % (index_name, table, ddl))
        print("  [ok]   索引 %s.%s 已创建" % (table, index_name))


def main():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("== 1. users 表新增 trust_score ==")
    add_column(cur, "users", "trust_score", "INT NOT NULL DEFAULT 0 COMMENT '信任分:成功归还+30,恶意认领-20'")

    print("== 2. lost_items / found_items 新增 phash ==")
    add_column(cur, "lost_items", "phash", "VARCHAR(16) DEFAULT NULL COMMENT '图片感知哈希(十六进制)'")
    add_column(cur, "found_items", "phash", "VARCHAR(16) DEFAULT NULL COMMENT '图片感知哈希(十六进制)'")

    print("== 3. found_items 新增 qa_json（密保问题）==")
    add_column(cur, "found_items", "qa_json", "TEXT COMMENT '密保问题JSON数组:[{\"q\":\"..\",\"a\":\"..\"},...]'")

    print("== 4. claim_records 新增 answers_json / auto_passed ==")
    add_column(cur, "claim_records", "answers_json", "TEXT COMMENT '认领时回答的密保答案JSON'")
    add_column(cur, "claim_records", "auto_passed", "TINYINT NOT NULL DEFAULT 0 COMMENT '是否密保评分自动通过(1=是)'")

    print("== 5. 新建 sessions 表 ==")
    if table_exists(cur, "sessions"):
        print("  [skip] sessions 表已存在")
    else:
        cur.execute(
            """CREATE TABLE sessions (
                 session_id VARCHAR(64) PRIMARY KEY,
                 user_id    INT NOT NULL,
                 expires_at DATETIME NOT NULL,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
               ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会话持久化表'"""
        )
        print("  [ok]   sessions 表已创建")

    print("== 6. 新建 notifications 表 ==")
    if table_exists(cur, "notifications"):
        print("  [skip] notifications 表已存在")
    else:
        cur.execute(
            """CREATE TABLE notifications (
                 id         INT AUTO_INCREMENT PRIMARY KEY,
                 user_id    INT NOT NULL,
                 type       VARCHAR(30) NOT NULL COMMENT 'new_item/claim_submitted/claim_result',
                 item_type  VARCHAR(10) DEFAULT NULL,
                 item_id    INT DEFAULT NULL,
                 message    VARCHAR(255) NOT NULL,
                 is_read    TINYINT NOT NULL DEFAULT 0,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 KEY idx_user_unread (user_id, is_read),
                 FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
               ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='轮询通知表'"""
        )
        print("  [ok]   notifications 表已创建")

    print("== 7. 索引 ==")
    for t in ("lost_items", "found_items"):
        add_index(cur, t, "idx_status_created", "(status, created_at)")
        add_index(cur, t, "idx_title", "(title)")
        add_index(cur, t, "idx_description", "(description(50))")

    conn.commit()
    cur.close()
    conn.close()
    print("\n迁移完成。")


if __name__ == "__main__":
    try:
        main()
    except Error as e:
        print("迁移失败:", e)
        raise

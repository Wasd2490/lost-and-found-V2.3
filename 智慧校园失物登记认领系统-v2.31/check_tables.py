import mysql.connector

conn = mysql.connector.connect(
    host='127.0.0.1', port=3306, user='root',
    password='wan1314xy', database='lost_and_found'
)
cur = conn.cursor()

# 检查所有表的字段
tables = ['claim_records', 'comments', 'notifications', 'sessions', 'delivery_tasks']
for t in tables:
    cur.execute(f"DESCRIBE {t}")
    cols = [r[0] for r in cur.fetchall()]
    print(f"{t}: {cols}")

conn.close()

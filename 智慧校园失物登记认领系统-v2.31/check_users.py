import mysql.connector

conn = mysql.connector.connect(
    host='127.0.0.1', port=3306, user='root',
    password='wan1314xy', database='lost_and_found'
)
cur = conn.cursor()
cur.execute("DESCRIBE users")
for r in cur.fetchall():
    print(r)
conn.close()

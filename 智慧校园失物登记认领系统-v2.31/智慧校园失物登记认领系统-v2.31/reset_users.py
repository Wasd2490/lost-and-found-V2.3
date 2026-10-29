import mysql.connector
import hashlib

conn = mysql.connector.connect(
    host='127.0.0.1', port=3306, user='root',
    password='wan1314xy', database='lost_and_found', autocommit=True
)
cur = conn.cursor()

# 1. 查看当前用户
cur.execute("SELECT id, username, role FROM users")
print("当前用户:", cur.fetchall())

# 2. 删除所有非管理员用户的相关数据
# 先获取非管理员用户ID
cur.execute("SELECT id FROM users WHERE role != 'admin'")
user_ids = [r[0] for r in cur.fetchall()]
print(f"非管理员用户ID: {user_ids}")

if user_ids:
    # 删除相关数据
    cur.execute("DELETE FROM comments WHERE user_id IN ({} )".format(','.join(['%s']*len(user_ids))), user_ids)
    print(f"删除评论: {cur.rowcount} 条")
    
    cur.execute("DELETE FROM claim_records WHERE claimer_id IN ({} )".format(','.join(['%s']*len(user_ids))), user_ids)
    print(f"删除认领记录: {cur.rowcount} 条")
    
    cur.execute("DELETE FROM lost_items WHERE user_id IN ({} )".format(','.join(['%s']*len(user_ids))), user_ids)
    print(f"删除失物: {cur.rowcount} 条")
    
    cur.execute("DELETE FROM found_items WHERE user_id IN ({} )".format(','.join(['%s']*len(user_ids))), user_ids)
    print(f"删除招领: {cur.rowcount} 条")
    
    cur.execute("DELETE FROM notifications WHERE user_id IN ({} )".format(','.join(['%s']*len(user_ids))), user_ids)
    print(f"删除通知: {cur.rowcount} 条")
    
    cur.execute("DELETE FROM sessions WHERE user_id IN ({} )".format(','.join(['%s']*len(user_ids))), user_ids)
    print(f"删除会话: {cur.rowcount} 条")
    
    # 删除用户
    cur.execute("DELETE FROM users WHERE id IN ({} )".format(','.join(['%s']*len(user_ids))), user_ids)
    print(f"删除用户: {cur.rowcount} 个")

# 3. 创建测试账号 user / 123456
password_hash = hashlib.sha256('123456'.encode()).hexdigest()
cur.execute("""
    INSERT INTO users (username, password_hash, real_name, student_id, college, class_name, phone, role, trust_score)
    VALUES (%s, %s, %s, %s, %s, %s, %s, 'user', 50)
    ON DUPLICATE KEY UPDATE password_hash = %s
""", ('user', password_hash, '测试用户', '20230001', '计算机学院', '软工2301', '13800138000', password_hash))
print("创建/更新测试账号: user / 123456")

# 4. 验证
cur.execute("SELECT id, username, role, real_name FROM users")
print("\n最终用户列表:")
for row in cur.fetchall():
    print(f"  ID={row[0]}, 用户名={row[1]}, 角色={row[2]}, 姓名={row[3]}")

conn.close()
print("\n完成！")

import mysql.connector

conn = mysql.connector.connect(
    host='127.0.0.1', port=3306, user='root',
    password='wan1314xy', database='lost_and_found', autocommit=True
)
cur = conn.cursor()

# 配送任务表
cur.execute('''CREATE TABLE IF NOT EXISTS delivery_tasks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  claim_id INT,
  item_type ENUM('lost','found') NOT NULL,
  item_id INT NOT NULL,
  sender_id INT NOT NULL,
  receiver_id INT NOT NULL,
  pickup_location VARCHAR(100) NOT NULL,
  dropoff_location VARCHAR(100) NOT NULL,
  vehicle_type ENUM('car','drone') DEFAULT 'car',
  status ENUM('pending','assigned','picked','delivering','delivered','failed') DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配送任务表' ''')
print('配送任务表已创建')

# 校园取件点表
cur.execute('''CREATE TABLE IF NOT EXISTS campus_points (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(50) NOT NULL,
  x_pos FLOAT NOT NULL,
  y_pos FLOAT NOT NULL,
  description VARCHAR(200)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='校园取件点' ''')
print('校园取件点表已创建')

# 插入预设取件点
points = [
    ('失物招领处', 0, 0, '行政楼一楼大厅'),
    ('一食堂', 50, 30, '一食堂门口'),
    ('图书馆', -20, 60, '图书馆正门'),
    ('宿舍区A', 80, -40, 'A区宿舍楼下'),
    ('教学楼B', 30, -70, 'B教学楼大厅'),
]
for p in points:
    cur.execute("INSERT INTO campus_points(name, x_pos, y_pos, description) VALUES(%s,%s,%s,%s)", p)
print('预设取件点已插入')

conn.close()

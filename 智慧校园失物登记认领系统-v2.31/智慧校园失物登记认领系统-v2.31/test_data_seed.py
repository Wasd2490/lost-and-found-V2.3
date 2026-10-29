import mysql.connector
import random
from datetime import datetime, timedelta

conn = mysql.connector.connect(
    host='127.0.0.1', port=3306, user='root',
    password='wan1314xy', database='lost_and_found', autocommit=True
)
cur = conn.cursor()

# 物品模板
lost_titles = [
    '校园卡（一卡通）', 'AirPods耳机', '宿舍钥匙', '高数课本', '蓝色保温杯',
    '黑色雨伞', '小米充电宝', '黑框眼镜', '灰色钱包', 'iPhone手机',
    '黑色双肩包', '食堂饭卡', '电动车钥匙', '英语四级词汇书', '粉色水杯',
    '白色帆布鞋', '罗技鼠标', '图书馆借阅证', '宿舍门禁卡', '保温杯套',
    '笔记本电脑', '蓝牙耳机盒', '自行车钥匙', '现代汉语词典', '透明雨伞',
    '华为充电器', '黑口罩', '公交卡', '红色外套', '蓝色笔记本',
    'U盘', '学生证', '宿舍储物柜钥匙', '物理习题集', '保温杯盖',
    '白色耳机线', '校园网账号卡', '自行车锁', '语文课本', '绿色水杯',
    '雨伞套', 'iPad', '钥匙串', '历史参考书', '黑色帽子',
    '保温杯（带吸管）', '银行卡', '宿舍柜子钥匙', '四六级真题', '透明文件袋'
]

found_titles = [
    '捡到一张校园卡', '捡到白色耳机', '捡到一串钥匙', '捡到一本数学书', '捡到一个水杯',
    '捡到一把黑色雨伞', '捡到一个充电宝', '捡到一副眼镜', '捡到一个钱包', '捡到一部手机',
    '捡到一个双肩包', '捡到一张饭卡', '捡到电动车钥匙', '捡到英语课本', '捡到粉色水杯',
    '捡到一只运动鞋', '捡到一个鼠标', '捡到借阅证', '捡到门禁卡', '捡到保温杯套',
    '捡到笔记本电脑', '捡到耳机充电盒', '捡到自行车钥匙', '捡到词典', '捡到透明雨伞',
    '捡到充电器', '捡到口罩', '捡到公交卡', '捡到一件外套', '捡到笔记本',
    '捡到一个U盘', '捡到学生证', '捡到柜子钥匙', '捡到习题集', '捡到杯盖',
    '捡到耳机线', '捡到校园网卡', '捡到自行车锁', '捡到语文书', '捡到绿色水杯',
    '捡到伞套', '捡到iPad', '捡到钥匙串', '捡到参考书', '捡到帽子',
    '捡到吸管水杯', '捡到银行卡', '捡到储物柜钥匙', '捡到真题集', '捡到文件袋'
]

categories = ['证件', '电子设备', '钥匙', '衣物', '书籍', '其他']
locations = [
    '一教101教室', '图书馆三楼', '一食堂', '二食堂', '男生宿舍3栋',
    '女生宿舍5栋', '操场看台', '体育馆', '图书馆二楼自习区', '教学楼B203',
    '大学生活动中心', '快递站', '校门口', '游泳馆门口', '实验楼A301',
    '一教205', '图书馆一楼大厅', '三食堂', '研究生宿舍', '篮球场旁',
    '体育馆更衣室', '图书馆四楼', '教学楼C102', '四食堂', '宿舍楼下长椅',
    '操场跑道', '网球场', '实验楼B202', '图书馆电子阅览室', '一教走廊长椅'
]

descriptions_lost = [
    '物品较新，对我很重要，捡到请联系我', '里面有重要的课表和笔记', '是在教室自习时落下的',
    '颜色比较特别，容易辨认', '已经找了两天了，很着急', '经常带在身上，突然找不到了',
    '上周还在用，这周就不见了', '里面有重要的个人信息', '希望好心人捡到归还',
    '对学习帮助很大，急求', '是生日礼物，意义重大', '已经补办了但还是想找到',
    '上面有名字标签', '放在书包侧袋里的', '中午在食堂吃饭时落下的',
    '图书馆借书时丢的', '骑车的时候掉的', '体育课休息时放在看台上',
    '晚自习结束就不见了', '坐公交时落下的'
]

descriptions_found = [
    '在教室捡到的，放在讲台上了', '在食堂座位上捡到的', '在图书馆自习区捡到',
    '在宿舍楼下长椅上捡到', '在操场看台上捡到的', '失主看到请联系我认领',
    '物品已交至招领处', '希望尽快找到失主', '里面有重要物品，请尽快认领',
    '放在保安室了', '是干净的，没有损坏', '已经放了好几天了',
    '今天下午刚捡到的', '在楼梯口捡到的', '失主可凭描述认领',
    '物品完好无损', '已拍照存档', '欢迎失主前来招领处认领',
    '是在自动售货机旁捡到的', '失主请描述物品特征领取'
]

# 插入失物数据（50条）
print("插入失物数据...")
for i in range(50):
    title = lost_titles[i % len(lost_titles)]
    cat = categories[i % len(categories)]
    loc = locations[i % len(locations)]
    desc = random.choice(descriptions_lost)
    days_ago = random.randint(1, 30)
    lost_time = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 12))
    phone = f"138{random.randint(10000000, 99999999)}"

    cur.execute(
        """INSERT INTO lost_items(user_id,title,description,category,location_lost,time_lost,contact,image_path,status,created_at)
           VALUES(%s,%s,%s,%s,%s,%s,%s,NULL,'approved',%s)""",
        (1, title, desc, cat, loc, lost_time, phone, lost_time)
    )

# 插入招领数据（50条）
print("插入招领数据...")
for i in range(50):
    title = found_titles[i % len(found_titles)]
    cat = categories[i % len(categories)]
    loc = locations[(i + 5) % len(locations)]
    desc = random.choice(descriptions_found)
    days_ago = random.randint(1, 25)
    found_time = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 12))
    phone = f"139{random.randint(10000000, 99999999)}"

    cur.execute(
        """INSERT INTO found_items(user_id,title,description,category,location_found,time_found,contact,image_path,status,created_at)
           VALUES(%s,%s,%s,%s,%s,%s,%s,NULL,'approved',%s)""",
        (1, title, desc, cat, loc, found_time, phone, found_time)
    )

# 验证
cur.execute("SELECT COUNT(*) FROM lost_items WHERE status='approved'")
lost_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM found_items WHERE status='approved'")
found_count = cur.fetchone()[0]
print(f"完成！失物启事：{lost_count} 条，招领启事：{found_count} 条")

conn.close()

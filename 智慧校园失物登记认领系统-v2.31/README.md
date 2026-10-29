# 智慧校园失物登记认领系统

基于原生 HTTP 的校园失物招领全栈应用，不使用任何 Web 框架。
支持陆空协同无人配送，集成 MicroROS 无人车控制。

---

## 一、项目技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 前端 | HTML + CSS + 原生 JavaScript + ECharts | fetch 发请求，无框架 |
| 后端 | Python 标准库 ThreadingHTTPServer | 多线程原生处理 HTTP 报文 |
| 数据库 | MySQL | 7 张业务表 |
| 会话 | Cookie + sessions 表 | 持久化会话，重启不丢登录 |
| 配送 | MicroROS 无人车 | 通过 HTTP 转发 /cmd_vel 指令 |
| 移动端 | PWA | manifest + Service Worker，可添加到主屏幕 |

---

## 二、目录结构

```
lost-and-found-v2/
├── server.py            # 后端主程序（所有路由）
├── db.py                # MySQL 连接封装
├── phash_util.py        # 以图搜图感知哈希工具
├── migrate_delivery.py   # 配送模块数据库迁移
├── init_db.py           # 首次初始化建库
├── reset_db.py          # 一键清空数据（保留表结构）
├── test_data_seed.py    # 测试数据生成脚本（50条失物+50条招领）
├── static/
│   ├── index.html       # 首页（轮播Banner + 寻物/招领列表 + 搜索 + 分页）
│   ├── login.html       # 登录
│   ├── register.html    # 注册（含学号/学院/班级/密保问题）
│   ├── post-lost.html   # 失物登记（带拍照上传）
│   ├── post-notice.html # 招领通知（带拍照上传 + 密保问题设置）
│   ├── post-found.html  # 领取确认（下拉选物品 + 表单）
│   ├── detail.html      # 物品详情（图片/联系方式/认领/评论/密保答题）
│   ├── my.html          # 我的记录（发布/认领列表）
│   ├── delivery.html    # 配送追踪（功能待开发，V3版本上线）
│   ├── admin.html       # 管理后台（审核/认领/用户/ECharts数据看板）
│   ├── manifest.json    # PWA 配置
│   ├── sw.js            # Service Worker 离线缓存
│   ├── css/style.css    # 全局样式
│   ├── js/common.js     # 公共 JS（api/导航/通知铃铛/工具）
│   ├── img/             # 轮播背景图
│   │   ├── slide1-sakura.jpg
│   │   ├── slide2-summer.jpg
│   │   └── slide3-campus.jpg
│   └── uploads/         # 上传图片目录
├── CHANGELOG.md         # 更新日志
└── README.md            # 本文件
```

---

## 三、快速启动

### 1. 准备 MySQL

修改 `db.py` 中的连接配置：

```python
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "你的MySQL密码",
    "database": "lost_and_found",
    "charset": "utf8mb4",
}
```

### 2. 初始化数据库

```bash
python init_db.py
python migrate_delivery.py    # 配送模块（首次运行）
```

自动建库、建表、插入管理员账号和预设取件点。

### 3. 启动服务器

```bash
python server.py
```

启动后会显示：
- 本机访问：`http://127.0.0.1:8000`
- 局域网访问：`http://你的局域网IP:8000`

---

## 四、默认账号

| 账号 | 密码 | 角色 |
|---|---|---|
| admin | admin123 | 管理员 |

普通用户在注册页自行注册（注册成功自动登录）。

---

## 五、功能说明

### 学生端

| 功能 | 说明 |
|---|---|
| 首页轮播 | 3张校园动漫背景自动轮播，展示系统特色功能 |
| 注册 | 用户名 + 密码 + 真实姓名 + 学号 + 学院 + 班级 + 手机号 + 密保问题 |
| 列表分页 | 每页20条，支持上一页/下一页/页码跳转 |
| 寻物/招领切换 | 双 Tab 切换，关键词搜索，**以图搜图**（上传照片匹配相似物品） |
| 失物登记 | 填写丢失物品信息，拍照上传，自动计算图片指纹 |
| 招领通知 | 填写捡到物品信息，拍照上传，可设置3个密保问题 |
| 物品详情 | 描述、照片、地点时间、联系方式（脱敏显示）、评论区、申请认领 |
| 申请认领 | 失主填写物品特征 + 回答密保问题，答对≥60%自动通过 |
| 领取确认 | 下拉选物品，确认后物品从首页消失（数据库保留） |
| 我的记录 | 我发布的、我认领的，寻物有"已找回"按钮 |
| 配送追踪 | 功能待开发，V3版本上线（陆空协同无人配送） |
| 消息通知 | 导航栏铃铛图标，未读红点，30秒轮询 |

### 管理员端（/admin.html）

| 功能 | 说明 |
|---|---|
| 数据看板 | ECharts 30天趋势折线图、物品分类饼图、关键指标卡片 |
| 刷新按钮 | 右上角"刷新数据"按钮，重新加载最新统计 |
| 待审核物品 | 通过 / 驳回 |
| 待处理认领 | 通过 / 拒绝，通过后物品自动标记已领取 |
| 用户列表 | 查看所有注册用户（姓名、学号、学院、班级、信任分） |

### 信任分体系

| 行为 | 分值变化 |
|---|---|
| 认领审核通过 | +30 分 |
| 认领审核驳回 | -20 分 |
| 高分用户（≥80） | 密保答对自动放行 |
| 低分用户（<40） | 需管理员人工审核 |

---

## 六、数据库表

| 表 | 主要字段 |
|---|---|
| users | id, username, password_hash, real_name, student_id, college, class_name, phone, role, trust_score, security_question |
| lost_items | id, user_id, title, description, category, location_lost, time_lost, contact, image_path, phash, status |
| found_items | id, user_id, title, description, category, location_found, time_found, contact, image_path, phash, security_answers, status |
| claim_records | id, item_type, item_id, user_id, claim_reason, security_answers, status |
| comments | id, item_type, item_id, user_id, content |
| sessions | session_id, user_id, expires_at |
| notifications | id, user_id, ntype, item_type, item_id, message, is_read |
| delivery_tasks | id, claim_id, item_type, item_id, sender_id, receiver_id, pickup_location, dropoff_location, vehicle_type, status |
| campus_points | id, name, x_pos, y_pos, description |

**物品状态流转**：`pending（待审核）` → `approved（已通过）` → `claimed（已找回）`，也可 `rejected（已驳回）`。

**配送状态流转**：`assigned（已派单）` → `picked（已取货）` → `delivering（配送中）` → `delivered（已送达）`。

---

## 七、API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/register | 注册（自动登录） |
| POST | /api/login | 登录 |
| POST | /api/logout | 退出 |
| GET | /api/me | 当前登录用户 |
| GET | /api/lost | 失物列表 |
| GET | /api/lost/{id} | 失物详情 |
| POST | /api/lost | 发布失物 |
| GET | /api/found | 招领列表 |
| GET | /api/found/{id} | 招领详情 |
| POST | /api/found | 发布招领 |
| POST | /api/claim | 提交认领（含密保答题） |
| POST | /api/recover | 用户确认领取 |
| POST | /api/upload | base64 图片上传 |
| POST | /api/search-by-image | 以图搜图（dHash） |
| GET | /api/comments | 评论列表 |
| POST | /api/comments | 发表评论 |
| GET | /api/my/posts | 我发布的 |
| GET | /api/my/claims | 我认领的 |
| GET | /api/notifications | 通知列表 |
| POST | /api/notifications/read-all | 全部已读 |
| GET | /api/delivery/points | 校园取件点列表 |
| GET | /api/delivery/my | 我的配送任务 |
| POST | /api/delivery/create | 创建配送任务 |
| POST | /api/delivery/car-control | 控制无人车移动 |
| PUT | /api/delivery/{id}/status | 更新配送状态 |
| GET | /api/admin/pending-items | 待审核物品 |
| GET | /api/admin/claims | 待处理认领 |
| GET | /api/admin/users | 用户列表 |
| GET | /api/admin/stats/trend | 30天发布趋势 |
| GET | /api/admin/stats/category | 物品分类统计 |
| PUT | /api/admin/item/{type}/{id}/status | 审核物品 |
| PUT | /api/admin/claim/{id}/status | 处理认领 |

---

## 八、无人车配送对接

### 对接 MicroROS 小车项目

本系统通过 HTTP 转发指令控制无人车，对接的是 `microros_car_project/web/car_web_server.py`。

**小车控制服务（在小车/虚拟机上运行）**：
```bash
cd microros_car_project/web
python car_web_server.py
# 默认端口 5000
```

**指令格式**：
```
POST http://<小车IP>:5000/cmd
Body: {"linear": 0.0, "angular": 0.0}
# linear: -1（后退）到 1（前进）
# angular: -1（右转）到 1（左转）
```

**本系统转发接口**：
```
POST /api/delivery/car-control
Body: {"linear": 0.5, "angular": 0.0}
# 自动转发到 http://127.0.0.1:5000/cmd
```

**小车未连接时**：系统自动降级为模拟模式，不影响其他功能。

---

## 九、外网访问配置

### 方案一：ngrok（推荐，长期稳定）

```bash
# 安装后配置 authtoken
ngrok config add-authtoken 你的token

# 启动隧道
ngrok http 8000
```

会生成一个 `https://xxxx.ngrok.io` 的公网地址，外网直接访问。

### 方案二：路由器端口转发

适合有公网IP的环境，路由器里把 8000 端口转发到本机局域网IP。

---

## 十、常见问题

| 问题 | 解决方法 |
|---|---|
| 启动报错 MySQL 连接失败 | 检查 db.py 里的密码，MySQL 服务是否启动 |
| 局域网其他电脑打不开 | 检查防火墙是否放行 8000 端口 |
| 上传照片不显示 | 检查 static/uploads/ 目录是否存在 |
| 以图搜图没结果 | 确认物品已通过审核，照片清晰 |
| 小车控制没反应 | 确认 car_web_server.py 已启动在 5000 端口 |
| 清空数据 | 运行 `python reset_db.py` |
| PWA 不显示安装按钮 | 需要 HTTPS 或 localhost 环境下访问 |

# 更新日志

## v2.3.0 - 2026-10-13（UI优化 + 分页 + 测试数据）

### UI优化
- **首页轮播Banner**：3张校园动漫背景图自动轮播，每5秒切换，左右箭头手动切换，底部圆点指示器
- **导航栏文字统一**：捡到物品→招领启事，丢失物品→寻物启事
- **Tab栏布局调整**：寻物启事/招领启事为切换Tab，领取登记为独立跳转按钮
- **配送追踪页**：改为"功能待开发，请等待V3版本"状态
- **轮播第三张**：陆空协同功能标注"功能待开发"

### 功能新增
- **列表分页**：首页寻物/招领列表每页20条，支持上一页/下一页/页码跳转
- **管理后台刷新按钮**：右上角"刷新数据"按钮，重新加载统计和图表
- **静态文件缓存控制**：所有静态文件加 no-cache 头，避免浏览器缓存旧版

### 新增脚本
- `test_data_seed.py`：测试数据生成脚本，一键插入50条失物+50条招领虚拟数据

---

## v2.2.0 - 2026-10-11（陆空协同配送模块）

### 新增功能
- **配送任务表** `delivery_tasks`：认领通过后可创建无人车配送任务
- **校园取件点表** `campus_points`：预设5个校园取件点（招领处/食堂/图书馆/宿舍/教学楼）
- **配送追踪页** `delivery.html`：校园地图、任务列表、小车遥控面板
- **小车控制接口** `POST /api/delivery/car-control`：转发指令到 MicroROS 小车 Web 服务（端口5000）
- **陆空协同调度**：支持无人车/无人机两种载具选择，未来可扩展无人机接口

### 技术对接
- 对接 MicroROS 小车项目 `car_web_server.py` 的 `/cmd` 接口
- 小车未连接时自动降级为模拟模式，不影响系统运行
- 5秒轮询刷新配送任务状态

---

## v2.1.0 - 2026-10-11（8项功能优化）

### P1 中期优化

#### 1. 以图搜图（dHash 感知哈希）
- 新建 `phash_util.py`：基于 PIL 实现 9×8 差异哈希（dHash），64 位特征压缩为 16 位 hex
- `lost_items` / `found_items` 新增 `phash` 字段，发布时自动计算并入库
- 新增 `POST /api/search-by-image`：上传图片，在已通过审核的招领库中按汉明距离 ≤10 检索相似物品
- 首页搜索栏右侧新增相机按钮，支持拍照/选图搜索，结果以卡片形式展示

#### 2. 实时通知（轮询）
- 新建 `notifications` 表（用户、类型、消息、已读状态）
- 触发事件：物品审核通过、新认领申请、认领审核结果
- 新增 `GET /api/notifications`、`POST /api/notifications/read-all`
- 前端导航栏新增铃铛图标，每 30 秒轮询，未读数红点提示，点击展开通知列表

#### 3. 认领密保问题 + 信任分
- `found_items` 新增 `qa_json` 字段，发布招领时可设置最多 3 组密保问题（问题+答案）
- `users` 新增 `trust_score` 字段（成功归还 +30，恶意/低分配率认领 -20）
- `claim_records` 新增 `answers_json`、`auto_passed` 字段
- 认领时回答密保问题，服务端按"双向包含"评分，正确率 ≥60% 自动通过并标记物品为已招领；<60% 转管理员审核
- 详情接口对非发布者/非管理员只返回问题不返回答案

#### 4. 管理后台 ECharts 看板
- 引入 ECharts 5 CDN
- 新增 `GET /api/stats/trend`（近 30 天每日发布量）、`GET /api/stats/category`（分类占比）
- admin.html 新增"近 30 天发布趋势"折线图、"分类占比"双饼图

### P2 长期优化

#### 5. PWA 改造
- 新建 `static/manifest.json`：可"添加到主屏幕"，standalone 模式
- 新建 `static/sw.js`：核心壳预缓存；HTML/CSS/JS 缓存优先，API/图片网络优先
- 所有页面 head 引入 manifest 与 theme-color；common.js 自动注册 Service Worker

#### 6. 隐私保护（手机号脱敏）
- 详情接口对非发布者、非管理员、且未成功认领的访问者，自动将联系方式脱敏：
  11 位手机号 → `138****5678`；其他格式 → 前 2 位 + `****` + 后 2 位
- 发布者本人、管理员、已通过认领的用户可见完整号码

#### 7. 会话持久化
- 新建 `sessions` 表（session_id、user_id、expires_at，7 天过期）
- 登录/注册时同时写库；服务器重启后自动从 DB 恢复有效会话，清理过期会话
- Cookie Max-Age 由 1 天延长到 7 天

#### 8. 数据库索引
- `lost_items` / `found_items` 新增复合索引 `idx_status_created(status, created_at)`
- 新增普通索引 `idx_title(title)`、`idx_description(description(50))`
- 迁移脚本：`migrate_v2.py`（幂等可重复执行）

### 其他
- 修复 server.py 中重复的空壳 `do_POST` 定义（死代码清理）
- MIME 类型新增 `.webmanifest` 支持
- 依赖：仅新增 Pillow（PIL），未引入任何 Web 框架

---

## v2.0.0 - 2026-10-11（安全与性能优化版）

### 性能优化
- 单线程 HTTPServer → 多线程 ThreadingHTTPServer，支持并发请求处理
- daemon_threads=True，主进程退出时自动清理子线程

### 安全加固
- 增加安全响应头：X-Content-Type-Options、X-Frame-Options、X-XSS-Protection
- 图片上传校验：5MB大小限制、格式白名单（jpeg/png/gif/webp）
- 文件名使用随机hex命名，防止路径遍历攻击
- SQL参数化查询（原版本已实现，保持）

### 技术栈
- 前端：原生 HTML/CSS/JavaScript
- 后端：Python ThreadingHTTPServer（多线程）
- 数据库：MySQL（5张表）
- 会话：Cookie SESSION_ID

---

## v1.0.0 - 2026-10-10（基础版）

### 新增功能
- 用户注册/登录/退出（Cookie会话）
- 注册字段：用户名、密码、真实姓名、学号、学院、班级、手机号
- 失物登记发布（支持拍照上传照片）
- 招领通知发布（支持拍照上传照片）
- 物品首页列表（双Tab切换寻物/招领）
- 关键词搜索
- 物品详情页（描述、照片、地点时间、联系方式）
- 物品评论区（朋友圈样式）
- 申请认领（填写物品特征）
- 领取确认（下拉选物品，标记已找回）
- 我的记录（我发布的、我认领的）
- 管理员后台（审核物品、处理认领、用户列表）
- 响应式移动端适配
- ngrok 内网穿透支持外网访问

### 数据库表
- users（用户表）
- lost_items（失物登记表）
- found_items（招领信息表）
- claim_records（认领记录表）
- comments（评论表）

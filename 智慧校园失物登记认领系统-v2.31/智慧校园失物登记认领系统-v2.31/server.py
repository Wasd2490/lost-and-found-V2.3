# -*- coding: utf-8 -*-
"""
基于原生 HTTP 的宿舍园区失物信息登记系统 - 后端服务器
====================================================
采用 Python 标准库 http.server 处理 HTTP 报文，
Cookie 维护登录会话,MySQL 存储业务数据。

启动:  python server.py
默认端口: 8000
"""
import json
import os
import re
import html
import base64
import hashlib
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import db
from phash_util import compute_phash, hamming

# ---------------- 配置 ----------------
PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 内存会话表: { session_id: user_id }
SESSIONS = {}

# 会话有效期 7 天（秒）
SESSION_MAX_AGE = 7 * 24 * 3600  # 604800

# 图片上传配置
ALLOWED_IMAGE_TYPES = {'jpeg', 'png', 'gif', 'webp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

# 静态文件 MIME 类型
MIME = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".svg":  "image/svg+xml",
    ".ico":  "image/x-icon",
}


def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()


def mask_phone(contact):
    """手机号/联系方式脱敏：11位手机号前3+****+后4；其他前2+****+后2。"""
    if not contact:
        return contact
    s = str(contact).strip()
    if not s:
        return s
    if re.fullmatch(r"\d{11}", s):
        return s[:3] + "****" + s[-4:]
    if len(s) <= 4:
        return s
    return s[:2] + "****" + s[-2:]


class Handler(BaseHTTPRequestHandler):
    # ---------- 基础工具 ----------
    def log_message(self, fmt, *args):
        # 简化日志
        print("[HTTP] %s - %s" % (self.address_string(), fmt % args))

    def _send_json(self, code, obj, extra_headers=None):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        # 安全响应头
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-XSS-Protection", "1; mode=block")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except Exception:
            # 兼容表单提交
            form = parse_qs(raw)
            return {k: v[0] for k, v in form.items()}

    def _parse_cookies(self):
        cookie = self.headers.get("Cookie", "")
        jar = {}
        for part in cookie.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                jar[k] = v
        return jar

    def _current_user(self):
        """根据 Cookie 中的 SESSION_ID 返回用户 dict，未登录返回 None"""
        sid = self._parse_cookies().get("SESSION_ID")
        if not sid or sid not in SESSIONS:
            return None
        uid = SESSIONS[sid]
        return db.query_one("SELECT id,username,real_name,student_id,college,class_name,role,phone,trust_score FROM users WHERE id=%s", (uid,))

    def _set_session_cookie(self, sid):
        return {"Set-Cookie": "SESSION_ID=%s; Path=/; HttpOnly; Max-Age=%d" % (sid, SESSION_MAX_AGE)}

    def _clear_session_cookie(self):
        return {"Set-Cookie": "SESSION_ID=; Path=/; HttpOnly; Max-Age=0"}

    # ---------- 通知辅助 ----------
    def _notify(self, user_id, ntype, item_type, item_id, message):
        """写入一条通知，失败不抛错（不影响主流程）。"""
        if not user_id:
            return
        try:
            db.execute(
                "INSERT INTO notifications(user_id,type,item_type,item_id,message,is_read) VALUES(%s,%s,%s,%s,%s,0)",
                (user_id, ntype, item_type, item_id, message),
            )
        except Exception as e:
            print("[notify] 写入失败:", e)

    # ---------- GET 路由分发：页面数据查询 ----------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        # favicon.ico 直接返回204，避免404报错
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # ===== 用户相关：当前登录信息 =====
        if path == "/api/me":
            return self._api_me()

        # ===== 失物/招领列表与详情 =====
        if path == "/api/lost":
            return self._api_lost_list(qs)
        if path.startswith("/api/lost/"):
            return self._api_lost_detail(path.split("/")[-1])
        if path == "/api/found":
            return self._api_found_list(qs)
        if path.startswith("/api/found/"):
            return self._api_found_detail(path.split("/")[-1])

        # ===== 我的记录：个人发布与认领 =====
        if path == "/api/my/posts":
            return self._api_my_posts()
        if path == "/api/my/claims":
            return self._api_my_claims()

        # ===== 评论区 =====
        if path == "/api/comments":
            return self._api_comments_list(qs)

        # ===== 通知中心 =====
        if path == "/api/notifications":
            return self._api_notifications()

        # ===== 统计（管理员） =====
        if path == "/api/stats/trend":
            return self._api_stats_trend()
        if path == "/api/stats/category":
            return self._api_stats_category()

        # ===== 管理员后台 =====
        if path == "/api/admin/pending-items":
            return self._api_admin_pending_items()
        if path == "/api/admin/claims":
            return self._api_admin_claims()
        if path == "/api/admin/users":
            return self._api_admin_users()

        # ===== 配送调度 =====
        if path == "/api/delivery/points":
            return self._api_delivery_points()
        if path == "/api/delivery/my":
            return self._api_delivery_my()
        m = re.match(r"^/api/delivery/(\d+)$", path)
        if m:
            return self._api_delivery_detail(int(m.group(1)))

        # ===== 静态文件 =====
        return self._serve_static(path)

    # ---------- POST 路由分发：提交数据 ----------
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        # ===== 用户认证：注册、登录、退出 =====
        if path == "/api/register":
            return self._api_register(body)
        if path == "/api/login":
            return self._api_login(body)
        if path == "/api/logout":
            return self._api_logout()

        # ===== 发布失物/招领信息 =====
        if path == "/api/lost":
            return self._api_lost_create(body)
        if path == "/api/found":
            return self._api_found_create(body)

        # ===== 认领申请与图片上传 =====
        if path == "/api/claim":
            return self._api_claim_create(body)
        if path == "/api/upload":
            return self._api_upload(body)

        # ===== 以图搜图 =====
        if path == "/api/search-by-image":
            return self._api_search_by_image(body)

        # ===== 通知已读 =====
        if path == "/api/notifications/read-all":
            return self._api_notifications_read_all()

        # ===== 发表评论 =====
        if path == "/api/comments":
            return self._api_comment_create(body)

        # ===== 用户确认领取/找回物品 =====
        if path == "/api/recover":
            return self._api_recover(body)

        # ===== 配送任务 =====
        if path == "/api/delivery/create":
            return self._api_delivery_create(body)
        if path == "/api/delivery/car-control":
            return self._api_car_control(body)

        self._send_json(404, {"error": "not found"})

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        # /api/admin/item/lost/5/status
        m = re.match(r"^/api/admin/item/(lost|found)/(\d+)/status$", path)
        if m:
            return self._api_admin_set_item_status(m.group(1), int(m.group(2)), body)
        # /api/admin/claim/3/status
        m = re.match(r"^/api/admin/claim/(\d+)/status$", path)
        if m:
            return self._api_admin_set_claim_status(int(m.group(1)), body)
        # /api/lost/5  (作者编辑)
        m = re.match(r"^/api/lost/(\d+)$", path)
        if m:
            return self._api_item_update("lost", int(m.group(1)), body)
        m = re.match(r"^/api/found/(\d+)$", path)
        if m:
            return self._api_item_update("found", int(m.group(1)), body)
        # /api/recover  (用户自己确认领取/找回物品)
        if path == "/api/recover":
            return self._api_recover(body)

        # /api/delivery/3/status  (更新配送状态)
        m = re.match(r"^/api/delivery/(\d+)/status$", path)
        if m:
            return self._api_delivery_set_status(int(m.group(1)), body)

        self._send_json(404, {"error": "not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        m = re.match(r"^/api/lost/(\d+)$", path)
        if m:
            return self._api_item_delete("lost", int(m.group(1)))
        m = re.match(r"^/api/found/(\d+)$", path)
        if m:
            return self._api_item_delete("found", int(m.group(1)))
        self._send_json(404, {"error": "not found"})

    # ---------- 静态文件 ----------
    def _serve_static(self, path):
        if path == "/":
            path = "/index.html"
        if path.startswith("/uploads/"):
            full = os.path.normpath(os.path.join(UPLOAD_DIR, path[len("/uploads/"):]))
            if not full.startswith(UPLOAD_DIR):
                self._send_json(403, {"error": "forbidden"})
                return
        else:
            full = os.path.normpath(os.path.join(STATIC_DIR, path.lstrip("/")))
            if not full.startswith(STATIC_DIR):
                self._send_json(403, {"error": "forbidden"})
                return
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("404 Not Found".encode("utf-8"))
            return
        ext = os.path.splitext(full)[1].lower()
        ctype = MIME.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(data)

    # ================================================================
    #  API 实现
    # ================================================================

    # ---- 认证 ----
    def _api_register(self, b):
        username = (b.get("username") or "").strip()
        password = b.get("password") or ""
        real_name = (b.get("real_name") or "").strip()
        student_id = (b.get("student_id") or "").strip()
        college = (b.get("college") or "").strip()
        class_name = (b.get("class_name") or "").strip()
        phone = (b.get("phone") or "").strip()
        if not username or not password:
            return self._send_json(400, {"error": "账号和密码不能为空"})
        if len(password) < 6:
            return self._send_json(400, {"error": "密码至少6位"})
        if not real_name:
            return self._send_json(400, {"error": "请填写真实姓名"})
        exist = db.query_one("SELECT id FROM users WHERE username=%s", (username,))
        if exist:
            return self._send_json(400, {"error": "该账号已被注册"})
        uid = db.execute(
            "INSERT INTO users(username,password_hash,real_name,student_id,college,class_name,phone,role) VALUES(%s,%s,%s,%s,%s,%s,%s,'user')",
            (username, hash_password(password), real_name, student_id, college, class_name, phone),
        )
        # 注册成功后自动登录，直接设置会话Cookie
        sid = secrets.token_hex(16)
        SESSIONS[sid] = uid
        # 持久化 session 到数据库
        try:
            db.execute(
                "INSERT INTO sessions(session_id,user_id,expires_at) VALUES(%s,%s,DATE_ADD(NOW(), INTERVAL 7 DAY))",
                (sid, uid),
            )
        except Exception as e:
            print("[session] 持久化失败:", e)
        return self._send_json(200, {"ok": True, "user_id": uid}, self._set_session_cookie(sid))

    def _api_login(self, b):
        username = (b.get("username") or "").strip()
        password = b.get("password") or ""
        row = db.query_one(
            "SELECT id,username,password_hash,role FROM users WHERE username=%s",
            (username,),
        )
        if not row or row["password_hash"] != hash_password(password or ""):
            return self._send_json(401, {"error": "账号或密码错误"})
        sid = secrets.token_hex(16)
        SESSIONS[sid] = row["id"]
        try:
            db.execute(
                "INSERT INTO sessions(session_id,user_id,expires_at) VALUES(%s,%s,DATE_ADD(NOW(), INTERVAL 7 DAY))",
                (sid, row["id"]),
            )
        except Exception as e:
            print("[session] 持久化失败:", e)
        return self._send_json(
            200,
            {"ok": True, "role": row["role"]},
            extra_headers=self._set_session_cookie(sid),
        )

    def _api_logout(self):
        sid = self._parse_cookies().get("SESSION_ID")
        if sid in SESSIONS:
            del SESSIONS[sid]
        try:
            db.execute("DELETE FROM sessions WHERE session_id=%s", (sid,))
        except Exception:
            pass
        return self._send_json(200, {"ok": True}, extra_headers=self._clear_session_cookie())

    def _api_me(self):
        u = self._current_user()
        if not u:
            return self._send_json(200, {"user": None})
        return self._send_json(200, {"user": u})

    # ---- 失物 ----
    def _api_lost_list(self, qs):
        where = ["status='approved'"]
        params = []
        kw = (qs.get("kw") or [""])[0].strip()
        cat = (qs.get("category") or [""])[0].strip()
        page = int((qs.get("page") or ["1"])[0])
        page_size = int((qs.get("page_size") or ["20"])[0])
        offset = (page - 1) * page_size
        if kw:
            where.append("(title LIKE %s OR description LIKE %s OR location_lost LIKE %s)")
            like = "%" + kw + "%"
            params += [like, like, like]
        if cat:
            where.append("category=%s")
            params.append(cat)
        where_sql = " AND ".join(where)
        total = db.query_one("SELECT COUNT(*) AS c FROM lost_items WHERE " + where_sql, tuple(params))["c"]
        sql = """SELECT l.*, u.real_name AS publisher_name
                 FROM lost_items l JOIN users u ON u.id=l.user_id
                 WHERE %s ORDER BY l.created_at DESC LIMIT %s OFFSET %s""" % (where_sql, page_size, offset)
        rows = db.query_all(sql, tuple(params))
        return self._send_json(200, {"list": rows, "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size})

    def _api_lost_detail(self, item_id):
        if not item_id.isdigit():
            return self._send_json(400, {"error": "bad id"})
        row = db.query_one(
            """SELECT l.*, u.real_name AS publisher_name
               FROM lost_items l JOIN users u ON u.id=l.user_id
               WHERE l.id=%s""",
            (int(item_id),),
        )
        if not row:
            return self._send_json(404, {"error": "not found"})
        # contact 脱敏
        u = self._current_user()
        is_owner = u and row["user_id"] == u["id"]
        is_admin = u and u.get("role") == "admin"
        can_full = bool(is_owner or is_admin)
        # 若该用户曾成功认领过该物品（lost 一般是本人找回，这里查 claim_records 兜底）
        if u and not can_full:
            claimed = db.query_one(
                "SELECT id FROM claim_records WHERE claimer_id=%s AND item_type='lost' AND item_id=%s AND status='approved' LIMIT 1",
                (u["id"], int(item_id)),
            )
            if claimed:
                can_full = True
        if not can_full:
            row["contact"] = mask_phone(row.get("contact"))
        return self._send_json(200, {"item": row})

    def _api_lost_create(self, b):
        u = self._current_user()
        if not u:
            return self._send_json(401, {"error": "请先登录"})
        title = (b.get("title") or "").strip()
        if not title:
            return self._send_json(400, {"error": "标题不能为空"})
        image_path = b.get("image_path") or None
        phash = compute_phash(image_path, STATIC_DIR) if image_path else None
        item_id = db.execute(
            """INSERT INTO lost_items(user_id,title,description,category,location_lost,time_lost,contact,image_path,phash)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                u["id"],
                title,
                b.get("description") or "",
                b.get("category") or "其他",
                b.get("location_lost") or "",
                b.get("time_lost") or None,
                b.get("contact") or u.get("phone") or "",
                image_path,
                phash,
            ),
        )
        return self._send_json(200, {"ok": True, "id": item_id})

    # ---- 招领 ----
    def _api_found_list(self, qs):
        where = ["status='approved'"]
        params = []
        kw = (qs.get("kw") or [""])[0].strip()
        cat = (qs.get("category") or [""])[0].strip()
        page = int((qs.get("page") or ["1"])[0])
        page_size = int((qs.get("page_size") or ["20"])[0])
        offset = (page - 1) * page_size
        if kw:
            where.append("(title LIKE %s OR description LIKE %s OR location_found LIKE %s)")
            like = "%" + kw + "%"
            params += [like, like, like]
        if cat:
            where.append("category=%s")
            params.append(cat)
        where_sql = " AND ".join(where)
        total = db.query_one("SELECT COUNT(*) AS c FROM found_items WHERE " + where_sql, tuple(params))["c"]
        sql = """SELECT f.*, u.real_name AS publisher_name
                 FROM found_items f JOIN users u ON u.id=f.user_id
                 WHERE %s ORDER BY f.created_at DESC LIMIT %s OFFSET %s""" % (where_sql, page_size, offset)
        rows = db.query_all(sql, tuple(params))
        return self._send_json(200, {"list": rows, "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size})

    def _api_found_detail(self, item_id):
        if not item_id.isdigit():
            return self._send_json(400, {"error": "bad id"})
        row = db.query_one(
            """SELECT f.*, u.real_name AS publisher_name
               FROM found_items f JOIN users u ON u.id=f.user_id
               WHERE f.id=%s""",
            (int(item_id),),
        )
        if not row:
            return self._send_json(404, {"error": "not found"})
        u = self._current_user()
        is_owner = u and row["user_id"] == u["id"]
        is_admin = u and u.get("role") == "admin"
        can_full = bool(is_owner or is_admin)
        # 若该用户已成功认领该物品，也可看完整 contact
        if u and not can_full:
            claimed = db.query_one(
                "SELECT id FROM claim_records WHERE claimer_id=%s AND item_type='found' AND item_id=%s AND status='approved' LIMIT 1",
                (u["id"], int(item_id)),
            )
            if claimed:
                can_full = True
        # qa 处理
        qa_raw = row.get("qa_json")
        qa_list = []
        if qa_raw:
            try:
                qa_list = json.loads(qa_raw) if isinstance(qa_raw, str) else (qa_raw or [])
            except Exception:
                qa_list = []
        if can_full:
            row["qa"] = qa_list
        else:
            row["qa"] = [{"q": q.get("q", "")} for q in qa_list if isinstance(q, dict)]
        # contact 脱敏
        if not can_full:
            row["contact"] = mask_phone(row.get("contact"))
        return self._send_json(200, {"item": row})

    def _api_found_create(self, b):
        u = self._current_user()
        if not u:
            return self._send_json(401, {"error": "请先登录"})
        title = (b.get("title") or "").strip()
        if not title:
            return self._send_json(400, {"error": "标题不能为空"})
        image_path = b.get("image_path") or None
        phash = compute_phash(image_path, STATIC_DIR) if image_path else None
        # 密保问题：最多 3 个，只保留非空 q/a 对
        qa_in = b.get("qa") or []
        qa_clean = []
        if isinstance(qa_in, list):
            for q in qa_in[:3]:
                if not isinstance(q, dict):
                    continue
                qq = (q.get("q") or "").strip()
                aa = (q.get("a") or "").strip()
                if qq and aa:
                    qa_clean.append({"q": qq, "a": aa})
        qa_json = json.dumps(qa_clean, ensure_ascii=False) if qa_clean else None
        item_id = db.execute(
            """INSERT INTO found_items(user_id,title,description,category,location_found,time_found,contact,image_path,phash,qa_json)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                u["id"],
                title,
                b.get("description") or "",
                b.get("category") or "其他",
                b.get("location_found") or "",
                b.get("time_found") or None,
                b.get("contact") or u.get("phone") or "",
                image_path,
                phash,
                qa_json,
            ),
        )
        return self._send_json(200, {"ok": True, "id": item_id})

    # ---- 编辑/删除 (作者本人或管理员) ----
    def _api_item_update(self, kind, item_id, b):
        u = self._current_user()
        if not u:
            return self._send_json(401, {"error": "请先登录"})
        table = "lost_items" if kind == "lost" else "found_items"
        row = db.query_one("SELECT user_id FROM %s WHERE id=%%s" % table, (item_id,))
        if not row:
            return self._send_json(404, {"error": "not found"})
        if row["user_id"] != u["id"] and u["role"] != "admin":
            return self._send_json(403, {"error": "无权修改"})
        fields = []
        params = []
        for k in ["title", "description", "category", "contact"]:
            if k in b:
                fields.append("%s=%%s" % k)
                params.append(b[k])
        if "location_lost" in b and kind == "lost":
            fields.append("location_lost=%s")
            params.append(b["location_lost"])
        if "location_found" in b and kind == "found":
            fields.append("location_found=%s")
            params.append(b["location_found"])
        if not fields:
            return self._send_json(200, {"ok": True})
        params.append(item_id)
        db.execute("UPDATE %s SET %s WHERE id=%%s" % (table, ",".join(fields)), tuple(params))
        return self._send_json(200, {"ok": True})

    def _api_recover(self, b):
        u = self._current_user()
        if not u:
            return self._send_json(401, {"error": "请先登录"})
        item_type = b.get("item_type", "lost")
        item_id = b.get("item_id")
        if not item_id:
            return self._send_json(400, {"error": "缺少物品ID"})
        table = "lost_items" if item_type == "lost" else "found_items"
        row = db.query_one("SELECT user_id FROM %s WHERE id=%%s" % table, (int(item_id),))
        if not row:
            return self._send_json(404, {"error": "物品不存在"})
        db.execute("UPDATE %s SET status='claimed' WHERE id=%%s" % table, (int(item_id),))
        return self._send_json(200, {"ok": True})

    def _api_item_delete(self, kind, item_id):
        u = self._current_user()
        if not u:
            return self._send_json(401, {"error": "请先登录"})
        table = "lost_items" if kind == "lost" else "found_items"
        row = db.query_one("SELECT user_id FROM %s WHERE id=%%s" % table, (item_id,))
        if not row:
            return self._send_json(404, {"error": "not found"})
        if row["user_id"] != u["id"] and u["role"] != "admin":
            return self._send_json(403, {"error": "无权删除"})
        db.execute("DELETE FROM %s WHERE id=%%s" % table, (item_id,))
        return self._send_json(200, {"ok": True})

    # ---- 我的 ----
    def _api_my_posts(self):
        u = self._current_user()
        if not u:
            return self._send_json(401, {"error": "请先登录"})
        lost = db.query_all("SELECT * FROM lost_items WHERE user_id=%s ORDER BY created_at DESC", (u["id"],))
        found = db.query_all("SELECT * FROM found_items WHERE user_id=%s ORDER BY created_at DESC", (u["id"],))
        return self._send_json(200, {"lost": lost, "found": found})

    def _api_my_claims(self):
        u = self._current_user()
        if not u:
            return self._send_json(401, {"error": "请先登录"})
        rows = db.query_all(
            """SELECT c.*, f.title AS item_title, f.location_found, f.time_found
               FROM claim_records c
               LEFT JOIN found_items f ON f.id=c.item_id
               WHERE c.claimer_id=%s ORDER BY c.created_at DESC""",
            (u["id"],),
        )
        return self._send_json(200, {"list": rows})

    # ---- 认领申请 ----
    def _api_claim_create(self, b):
        u = self._current_user()
        if not u:
            return self._send_json(401, {"error": "请先登录"})
        item_id = b.get("item_id")
        item_type = b.get("item_type", "found")
        reason = (b.get("claim_reason") or "").strip()
        if not item_id or not reason:
            return self._send_json(400, {"error": "请填写认领理由/物品特征"})
        # 只能对已通过的招领/失物发起认领
        table = "found_items" if item_type == "found" else "lost_items"
        item = db.query_one(
            "SELECT id,user_id,status,title,qa_json FROM %s WHERE id=%%s" % table,
            (int(item_id),),
        )
        if not item:
            return self._send_json(404, {"error": "物品不存在"})
        if item["status"] != "approved":
            return self._send_json(400, {"error": "该物品尚未通过审核，无法认领"})
        if item["user_id"] == u["id"]:
            return self._send_json(400, {"error": "不能认领自己发布的物品"})

        # 解析密保问题（仅 found 有）
        qa_list = []
        if item_type == "found" and item.get("qa_json"):
            try:
                qa_list = json.loads(item["qa_json"]) if isinstance(item["qa_json"], str) else (item["qa_json"] or [])
            except Exception:
                qa_list = []

        answers = b.get("answers") or []
        answers_json = json.dumps(answers, ensure_ascii=False) if answers else None

        auto_passed = 0
        score_ratio = 0.0
        if qa_list:
            # 评分
            correct = 0
            total = len(qa_list)
            for idx, q in enumerate(qa_list):
                std = (q.get("a") or "").strip().lower() if isinstance(q, dict) else ""
                user_ans = ""
                if idx < len(answers):
                    user_ans = str(answers[idx] or "").strip().lower()
                if std and user_ans and (std in user_ans or user_ans in std):
                    correct += 1
            score_ratio = correct / total if total else 0.0
            if score_ratio >= 0.6:
                auto_passed = 1

        if auto_passed:
            # 自动通过
            cid = db.execute(
                """INSERT INTO claim_records(claimer_id,item_type,item_id,claim_reason,status,answers_json,auto_passed,admin_id,processed_at)
                   VALUES(%s,%s,%s,%s,'approved',%s,1,NULL,NOW())""",
                (u["id"], item_type, int(item_id), reason, answers_json),
            )
            db.execute("UPDATE %s SET status='claimed' WHERE id=%%s" % table, (int(item_id),))
            db.execute("UPDATE users SET trust_score = trust_score + 30 WHERE id=%s", (u["id"],))
            self._notify(
                item["user_id"], "claim_auto_pass", item_type, int(item_id),
                "密保验证通过，「%s」已标记为招领" % item["title"],
            )
            return self._send_json(200, {"ok": True, "id": cid, "auto_passed": True, "score": score_ratio})
        else:
            # 保持 pending
            cid = db.execute(
                "INSERT INTO claim_records(claimer_id,item_type,item_id,claim_reason,status,answers_json,auto_passed) VALUES(%s,%s,%s,%s,'pending',%s,0)",
                (u["id"], item_type, int(item_id), reason, answers_json),
            )
            if qa_list:
                # 密保不符，扣 trust_score
                db.execute("UPDATE users SET trust_score = trust_score - 20 WHERE id=%s", (u["id"],))
                self._notify(
                    item["user_id"], "claim_qa_fail", item_type, int(item_id),
                    "有人提交认领「%s」但密保答案不符，等待审核" % item["title"],
                )
            else:
                self._notify(
                    item["user_id"], "claim_new", item_type, int(item_id),
                    "有人申请认领你的「%s」" % item["title"],
                )
            return self._send_json(200, {"ok": True, "id": cid, "auto_passed": False, "score": score_ratio})

    def _api_upload(self, b):
        u = self._current_user()
        if not u:
            return self._send_json(401, {"error": "请先登录"})
        data_url = b.get("image") or ""
        if not data_url.startswith("data:image/"):
            return self._send_json(400, {"error": "图片格式错误"})
        try:
            header, encoded = data_url.split(",", 1)
            ext = "jpg"
            if "png" in header: ext = "png"
            elif "webp" in header: ext = "webp"
            raw = base64.b64decode(encoded)
            if len(raw) > 5 * 1024 * 1024:
                return self._send_json(400, {"error": "图片不能超过5MB"})
            fname = secrets.token_hex(8) + "." + ext
            fpath = os.path.join(UPLOAD_DIR, fname)
            with open(fpath, "wb") as f:
                f.write(raw)
            return self._send_json(200, {"ok": True, "path": "/uploads/" + fname})
        except Exception as e:
            return self._send_json(500, {"error": "上传失败: " + str(e)})

    # ---- 以图搜图 ----
    def _api_search_by_image(self, b):
        # 允许未登录匿名搜图（按需求未要求登录），但容错处理
        data_url = b.get("image") or ""
        target_hash = None
        if data_url.startswith("data:image/"):
            try:
                header, encoded = data_url.split(",", 1)
                ext = "jpg"
                if "png" in header: ext = "png"
                elif "webp" in header: ext = "webp"
                raw = base64.b64decode(encoded)
                fname = "search_" + secrets.token_hex(8) + "." + ext
                fpath = os.path.join(UPLOAD_DIR, fname)
                with open(fpath, "wb") as f:
                    f.write(raw)
                target_hash = compute_phash("/uploads/" + fname, STATIC_DIR)
            except Exception:
                target_hash = None
        if not target_hash:
            return self._send_json(200, {"list": []})
        # 查询所有 approved 且 phash 非空的 found_items
        rows = db.query_all(
            """SELECT f.*, u.real_name AS publisher_name
               FROM found_items f JOIN users u ON u.id=f.user_id
               WHERE f.status='approved' AND f.phash IS NOT NULL AND f.phash<>''"""
        )
        matched = []
        for r in rows:
            d = hamming(target_hash, r.get("phash"))
            if d <= 10:
                r["distance"] = d
                matched.append(r)
        matched.sort(key=lambda x: x["distance"])
        return self._send_json(200, {"list": matched})

    # ---- 通知 ----
    def _api_notifications(self):
        u = self._current_user()
        if not u:
            return self._send_json(401, {"error": "请先登录"})
        rows = db.query_all(
            "SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 30",
            (u["id"],),
        )
        unread = db.query_one(
            "SELECT COUNT(*) AS c FROM notifications WHERE user_id=%s AND is_read=0",
            (u["id"],),
        )
        return self._send_json(200, {"list": rows, "unread_count": unread["c"] if unread else 0})

    def _api_notifications_read_all(self):
        u = self._current_user()
        if not u:
            return self._send_json(401, {"error": "请先登录"})
        db.execute("UPDATE notifications SET is_read=1 WHERE user_id=%s AND is_read=0", (u["id"],))
        return self._send_json(200, {"ok": True})

    # ---- 评论区 ----
    def _api_comments_list(self, qs):
        item_type = (qs.get("type") or ["lost"])[0]
        item_id = (qs.get("item_id") or ["0"])[0]
        if not item_id.isdigit():
            return self._send_json(400, {"error": "bad item_id"})
        rows = db.query_all(
            """SELECT c.*, u.real_name, u.username
               FROM comments c JOIN users u ON u.id=c.user_id
               WHERE c.item_type=%s AND c.item_id=%s
               ORDER BY c.created_at ASC""",
            (item_type, int(item_id)),
        )
        return self._send_json(200, {"list": rows})

    def _api_comment_create(self, b):
        u = self._current_user()
        if not u:
            return self._send_json(401, {"error": "请先登录后留言"})
        item_type = b.get("item_type", "lost")
        item_id = b.get("item_id")
        content = (b.get("content") or "").strip()
        if not item_id or not content:
            return self._send_json(400, {"error": "留言内容不能为空"})
        if len(content) > 500:
            return self._send_json(400, {"error": "留言不能超过500字"})
        cid = db.execute(
            "INSERT INTO comments(item_type,item_id,user_id,content) VALUES(%s,%s,%s,%s)",
            (item_type, int(item_id), u["id"], content),
        )
        return self._send_json(200, {"ok": True, "id": cid})

    # ---- 管理员 ----
    def _require_admin(self):
        u = self._current_user()
        if not u:
            self._send_json(401, {"error": "请先登录"})
            return None
        if u["role"] != "admin":
            self._send_json(403, {"error": "需要管理员权限"})
            return None
        return u

    def _api_admin_pending_items(self):
        if not self._require_admin():
            return
        lost = db.query_all(
            """SELECT l.*, u.real_name AS publisher_name FROM lost_items l
               JOIN users u ON u.id=l.user_id WHERE l.status='pending'
               ORDER BY l.created_at DESC"""
        )
        found = db.query_all(
            """SELECT f.*, u.real_name AS publisher_name FROM found_items f
               JOIN users u ON u.id=f.user_id WHERE f.status='pending'
               ORDER BY f.created_at DESC"""
        )
        return self._send_json(200, {"lost": lost, "found": found})

    def _api_admin_set_item_status(self, kind, item_id, b):
        if not self._require_admin():
            return
        status = b.get("status")
        if status not in ("approved", "rejected", "claimed", "pending"):
            return self._send_json(400, {"error": "bad status"})
        table = "lost_items" if kind == "lost" else "found_items"
        # 查出物品发布者与标题用于通知
        item = db.query_one("SELECT user_id,title FROM %s WHERE id=%%s" % table, (item_id,))
        db.execute("UPDATE %s SET status=%%s WHERE id=%%s" % table, (status, item_id))
        if item and status == "approved":
            self._notify(
                item["user_id"], "item_approved", kind, item_id,
                "你的「%s」已通过审核" % item["title"],
            )
        return self._send_json(200, {"ok": True})

    def _api_admin_claims(self):
        if not self._require_admin():
            return
        rows = db.query_all(
            """SELECT c.*, u.real_name AS claimer_name, u.phone AS claimer_phone,
                      f.title AS item_title, f.location_found, f.time_found, f.contact
               FROM claim_records c
               JOIN users u ON u.id=c.claimer_id
               LEFT JOIN found_items f ON f.id=c.item_id
               ORDER BY (c.status='pending') DESC, c.created_at DESC"""
        )
        return self._send_json(200, {"list": rows})

    def _api_admin_set_claim_status(self, claim_id, b):
        admin = self._require_admin()
        if not admin:
            return
        status = b.get("status")
        if status not in ("approved", "rejected"):
            return self._send_json(400, {"error": "bad status"})
        rec = db.query_one("SELECT item_type,item_id,claimer_id FROM claim_records WHERE id=%s", (claim_id,))
        if not rec:
            return self._send_json(404, {"error": "not found"})
        db.execute(
            "UPDATE claim_records SET status=%s, admin_id=%s, processed_at=NOW() WHERE id=%s",
            (status, admin["id"], claim_id),
        )
        # 若认领通过,把对应物品标记为已认领
        if status == "approved":
            table = "found_items" if rec["item_type"] == "found" else "lost_items"
            db.execute("UPDATE %s SET status='claimed' WHERE id=%%s" % table, (rec["item_id"],))
            # 给认领人加信任分
            db.execute("UPDATE users SET trust_score = trust_score + 30 WHERE id=%s", (rec["claimer_id"],))
            self._notify(rec["claimer_id"], "claim_approved", rec["item_type"], rec["item_id"], "你的认领申请已通过")
        else:
            db.execute("UPDATE users SET trust_score = trust_score - 20 WHERE id=%s", (rec["claimer_id"],))
            self._notify(rec["claimer_id"], "claim_rejected", rec["item_type"], rec["item_id"], "你的认领申请被驳回")
        return self._send_json(200, {"ok": True})

    def _api_admin_users(self):
        if not self._require_admin():
            return
        rows = db.query_all(
            "SELECT id,username,real_name,role,phone,trust_score,created_at FROM users ORDER BY id"
        )
        return self._send_json(200, {"list": rows})

    # ---- 统计（管理员） ----
    def _api_stats_trend(self):
        if not self._require_admin():
            return
        lost_rows = db.query_all(
            """SELECT DATE(created_at) d, COUNT(*) c
               FROM lost_items
               WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
               GROUP BY DATE(created_at)"""
        )
        found_rows = db.query_all(
            """SELECT DATE(created_at) d, COUNT(*) c
               FROM found_items
               WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
               GROUP BY DATE(created_at)"""
        )
        # 生成近30天日期列表
        date_map_lost = {str(r["d"]): r["c"] for r in lost_rows}
        date_map_found = {str(r["d"]): r["c"] for r in found_rows}
        days = []
        lost_arr = []
        found_arr = []
        for i in range(29, -1, -1):
            d_row = db.query_one("SELECT DATE(DATE_SUB(CURDATE(), INTERVAL %s DAY)) AS d", (i,))
            d_str = str(d_row["d"]) if d_row else ""
            days.append(d_str)
            lost_arr.append(date_map_lost.get(d_str, 0))
            found_arr.append(date_map_found.get(d_str, 0))
        return self._send_json(200, {"days": days, "lost": lost_arr, "found": found_arr})

    def _api_stats_category(self):
        if not self._require_admin():
            return
        lost_rows = db.query_all(
            "SELECT category AS name, COUNT(*) AS value FROM lost_items GROUP BY category"
        )
        found_rows = db.query_all(
            "SELECT category AS name, COUNT(*) AS value FROM found_items GROUP BY category"
        )
        return self._send_json(200, {"lost": lost_rows, "found": found_rows, "list": found_rows})

    # ==================== 配送调度模块 ====================

    def _api_delivery_points(self):
        rows = db.query_all("SELECT id,name,x_pos,y_pos,description FROM campus_points ORDER BY id")
        return self._send_json(200, {"list": rows})

    def _api_delivery_my(self):
        user = self._require_login()
        if not user:
            return
        rows = db.query_all(
            """SELECT d.*, u1.real_name AS sender_name, u2.real_name AS receiver_name,
                      f.title AS item_title
               FROM delivery_tasks d
               LEFT JOIN users u1 ON d.sender_id=u1.id
               LEFT JOIN users u2 ON d.receiver_id=u2.id
               LEFT JOIN found_items f ON d.item_type='found' AND d.item_id=f.id
               WHERE d.sender_id=%s OR d.receiver_id=%s
               ORDER BY d.created_at DESC""",
            (user["id"], user["id"])
        )
        return self._send_json(200, {"list": rows})

    def _api_delivery_detail(self, task_id):
        user = self._require_login()
        if not user:
            return
        row = db.query_one(
            "SELECT * FROM delivery_tasks WHERE id=%s", (task_id,)
        )
        if not row:
            return self._send_json(404, {"error": "任务不存在"})
        return self._send_json(200, {"task": row})

    def _api_delivery_create(self, body):
        user = self._require_login()
        if not user:
            return
        claim_id = body.get("claim_id")
        pickup = body.get("pickup_location")
        dropoff = body.get("dropoff_location")
        vehicle = body.get("vehicle_type", "car")

        claim = db.query_one("SELECT * FROM claim_records WHERE id=%s", (claim_id,))
        if not claim or claim["status"] != "approved":
            return self._send_json(400, {"error": "认领未通过，无法创建配送"})

        task_id = db.execute(
            """INSERT INTO delivery_tasks
               (claim_id, item_type, item_id, sender_id, receiver_id,
                pickup_location, dropoff_location, vehicle_type, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'assigned')""",
            (claim_id, claim["item_type"], claim["item_id"],
             user["id"], claim["claimer_id"], pickup, dropoff, vehicle)
        )
        return self._send_json(200, {"task_id": task_id, "ok": True})

    def _api_delivery_set_status(self, task_id, body):
        user = self._require_login()
        if not user:
            return
        status = body.get("status")
        if status not in ("assigned", "picked", "delivering", "delivered", "failed"):
            return self._send_json(400, {"error": "bad status"})
        db.execute(
            "UPDATE delivery_tasks SET status=%s WHERE id=%s",
            (status, task_id)
        )
        return self._send_json(200, {"ok": True})

    def _api_car_control(self, body):
        """调用小车Web接口控制移动"""
        import urllib.request
        linear = body.get("linear", 0)
        angular = body.get("angular", 0)
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:5000/cmd",
                data=json.dumps({"linear": linear, "angular": angular}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                return self._send_json(200, json.loads(resp.read()))
        except Exception as e:
            return self._send_json(200, {"status": "simulated", "error": str(e),
                                         "msg": "小车未连接，使用模拟模式"})


def _load_sessions_from_db():
    """启动时从数据库恢复有效 session，并清理过期 session。"""
    try:
        db.execute("DELETE FROM sessions WHERE expires_at <= NOW()")
        rows = db.query_all("SELECT session_id, user_id FROM sessions WHERE expires_at > NOW()")
        for r in rows:
            SESSIONS[r["session_id"]] = r["user_id"]
        print("[session] 从数据库恢复有效会话 %d 条" % len(rows))
    except Exception as e:
        print("[session] 启动加载失败（忽略）:", e)


def main():
    import socket
    # 启动前加载持久化 session
    _load_sessions_from_db()
    # 获取本机局域网IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip = "127.0.0.1"
    print("=" * 60)
    print(" 智慧校园失物登记认领系统 后端启动中...")
    print(" 本机访问:   http://127.0.0.1:%d" % PORT)
    print(" 局域网访问: http://%s:%d" % (lan_ip, PORT))
    print(" 管理员账号: admin / admin123")
    print("=" * 60)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
pHash (dHash) 以图搜图辅助模块
================================
仅依赖 Pillow，不使用 imagehash。
"""
import os
from PIL import Image

# 与 server.py 中保持一致，避免循环引用时直接传 STATIC_DIR
DEFAULT_STATIC_DIR = None


def _resolve_path(image_path, static_dir=None):
    """把 "/uploads/xxx.jpg" 解析成磁盘绝对路径。"""
    if image_path is None:
        return None
    if os.path.isabs(image_path):
        return image_path
    base = static_dir or DEFAULT_STATIC_DIR
    if base is None:
        # 兜底：基于本文件位置推断 static 目录
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    return os.path.normpath(os.path.join(base, image_path.lstrip("/")))


def compute_phash(image_path, static_dir=None):
    """
    计算图片的 64 位 dHash，返回 16 位小写 hex 字符串；失败返回 None。
    规则：
      - 转灰度
      - 缩放到 9x8（得到 8 行 x 9 列）
      - 每行相邻像素左>=右记 1，否则记 0，共 8*8=64 位
      - 转成 16 位 hex
    """
    p = _resolve_path(image_path, static_dir)
    if not p or not os.path.isfile(p):
        return None
    try:
        with Image.open(p) as im:
            im = im.convert("L").resize((9, 8), Image.LANCZOS)
            pixels = list(im.getdata())  # 72 个像素
        bits = []
        for r in range(8):
            row = pixels[r * 9:(r + 1) * 9]
            for c in range(8):
                bits.append('1' if row[c] >= row[c + 1] else '0')
        bit_str = "".join(bits)
        # 64 位二进制 -> 16 位 hex
        return "%016x" % int(bit_str, 2)
    except Exception:
        return None


def hamming(h1, h2):
    """两个 16 位 hex 串的汉明距离（异或后数 1 的个数）。"""
    if not h1 or not h2:
        return 64
    try:
        return bin(int(h1, 16) ^ int(h2, 16)).count("1")
    except Exception:
        return 64

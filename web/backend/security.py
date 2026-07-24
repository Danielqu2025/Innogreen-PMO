"""密码哈希 - Phase C 鉴权（bcrypt 直接调用，避免 passlib 抽象层）"""
from __future__ import annotations

import bcrypt

# bcrypt 截断 72 字节密码；超长显式拒绝，避免静默截断带来的安全错觉。
_MAX_PASSWORD_BYTES = 72
_ROUNDS = 12

# 与 bootstrap / UserCreate 共用：拒绝明显弱口令与 .env.example 示例值
WEAK_PASSWORDS = frozenset(
    {
        "change-me-now",
        "change-me",
        "password",
        "admin",
        "admin123",
        "12345678",
        "password123",
    }
)


def is_weak_password(password: str) -> bool:
    """明显弱口令或 change-me* 示例前缀 → True（大小写不敏感）。"""
    p = password.lower()
    return p in WEAK_PASSWORDS or p.startswith("change-me")


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")
    if len(pw) > _MAX_PASSWORD_BYTES:
        raise ValueError("密码过长（>72 字节）")
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=_ROUNDS)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    pw = password.encode("utf-8")
    # bcrypt.checkpw 自身处理 >72 字节（截断），这里与哈希时一致即可。
    try:
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except ValueError:
        # 无效哈希格式（如脏数据）→ 视为校验失败，不向上抛
        return False

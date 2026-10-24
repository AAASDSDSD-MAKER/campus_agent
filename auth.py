"""注册 / 登录：PBKDF2 + 随机盐。"""
import hashlib
import secrets

from . import db


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(

        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000
    ).hex()


def register(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if not (3 <= len(username) <= 20):
        return False, "用户名长度需在 3~20 之间"
    if len(password) < 6:
        return False, "密码至少 6 位"
    if db.get_user_by_name(username):
        return False, "该用户名已被注册"
    salt = secrets.token_hex(16)
    db.create_user(username, _hash(password, salt), salt)
    return True, "注册成功，请登录"


def login(username: str, password: str) -> tuple[bool, str, dict | None]:
    user = db.get_user_by_name(username.strip())
    if not user:
        return False, "用户不存在", None
    if _hash(password, user["salt"]) != user["password_hash"]:
        return False, "密码错误", None
    return True, "登录成功", dict(user)
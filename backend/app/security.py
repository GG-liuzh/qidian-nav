import base64
import hashlib
import hmac
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from .db import now
from .models import RateBucket

passwords = PasswordHasher()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(encoded: str, supplied: str) -> bool:
    try:
        return passwords.verify(encoded, supplied)
    except (VerificationError, InvalidHashError):
        return False


def constant_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())


class Vault:
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("凭据密钥必须为 32 字节；请运行初始化命令。")
        self.cipher = AESGCM(key)
        self.key_id = hashlib.sha256(key).hexdigest()[:24]

    def encrypt(self, value: str, credential_id: str, endpoint_id: str, field: str):
        nonce = secrets.token_bytes(12)
        aad = f"{credential_id}:{endpoint_id}:{field}".encode()
        ciphertext = self.cipher.encrypt(nonce, value.encode(), aad)
        return base64.b64encode(ciphertext).decode(), base64.b64encode(nonce).decode()

    def decrypt(self, credential, field: str) -> str:
        if credential.key_id != self.key_id:
            raise HTTPException(503, "凭据密钥不可用，请联系部署管理员。")
        aad = f"{credential.id}:{credential.endpoint_id}:{field}".encode()
        try:
            return self.cipher.decrypt(
                base64.b64decode(getattr(credential, f"{field}_nonce")),
                base64.b64decode(getattr(credential, f"{field}_ciphertext")),
                aad,
            ).decode()
        except Exception:
            raise HTTPException(503, "凭据校验失败，请联系维护人。") from None


def rate_limit(request, key: str, limit: int, seconds: int = 60):
    if not request.app.state.settings.rate_limit_enabled:
        return
    # A separate short transaction retains failed attempts and works across workers.
    factory = request.app.state.sessions
    hashed = digest(key)
    with factory.begin() as db:
        try:
            with db.begin_nested():
                db.add(RateBucket(key=hashed, count=0, reset_at=now() + timedelta(seconds=seconds)))
                db.flush()
        except IntegrityError:
            pass
        db.execute(
            update(RateBucket)
            .where(RateBucket.key == hashed, RateBucket.reset_at <= now())
            .values(count=0, reset_at=now() + timedelta(seconds=seconds))
        )
        count = db.execute(
            update(RateBucket)
            .where(RateBucket.key == hashed)
            .values(count=RateBucket.count + 1)
            .returning(RateBucket.count)
        ).scalar_one()
        db.execute(RateBucket.__table__.delete().where(RateBucket.reset_at < now() - timedelta(days=1)))
    if count > limit:
        raise HTTPException(429, "操作过于频繁，请稍后再试。", headers={"Retry-After": str(seconds)})

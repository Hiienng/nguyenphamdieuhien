from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from ..core.config import get_settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str) -> str:
    s = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=s.JWT_ACCESS_EXPIRE_MIN)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "access"}, s.JWT_SECRET_KEY, algorithm=s.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    s = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=s.JWT_REFRESH_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "refresh"}, s.JWT_SECRET_KEY, algorithm=s.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        s = get_settings()
        return jwt.decode(token, s.JWT_SECRET_KEY, algorithms=[s.JWT_ALGORITHM])
    except JWTError:
        return None

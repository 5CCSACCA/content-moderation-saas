import os
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

# JWT configuration. In production, JWT_SECRET should be a long, random,
# securely-stored value — never commit a real secret to source control.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(user_id: str, role: str) -> str:
    """Creates a signed JWT containing the user's id and role, with an
    expiry claim. Downstream services can verify this token's signature
    and read the role claim to enforce RBAC without querying the database."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jose.JWTError if the token is invalid, expired, or tampered with."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
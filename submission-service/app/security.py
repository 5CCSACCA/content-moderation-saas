import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

# Must match the JWT_SECRET used by auth-service to sign tokens — both
# services share this value via the same environment variable so that
# tokens issued by auth-service can be verified here without a network
# call back to auth-service on every request.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"

bearer_scheme = HTTPBearer()


class CurrentUser:
    def __init__(self, user_id: str, role: str):
        self.user_id = user_id
        self.role = role


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    """FastAPI dependency that verifies the JWT on incoming requests and
    returns the authenticated user's id and role. Raises 401 if the token
    is missing, invalid, expired, or tampered with."""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return CurrentUser(user_id=payload["sub"], role=payload["role"])
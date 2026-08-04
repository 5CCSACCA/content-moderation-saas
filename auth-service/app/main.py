from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, ProgrammingError

from .database import get_db, engine
from .models import Base, User
from .schemas import TokenResponse, UserLogin, UserRegister, UserResponse
from .security import create_access_token, decode_access_token, hash_password, verify_password

app = FastAPI(title="Auth Service", version="0.1.0")

from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)

# Create tables on startup if they don't already exist. For a coursework
# project this keeps deployment to a single command; a production system
# would use a proper migration tool (e.g. Alembic) instead.

try:
    Base.metadata.create_all(bind=engine)
except (IntegrityError, ProgrammingError):
    # Harmless race condition: another service instance or a container
    # restart attempted table creation concurrently and won first. The
    # tables exist either way, so this is safe to ignore.
    pass

bearer_scheme = HTTPBearer()


@app.get("/health")
def health():
    """Basic health check endpoint used by Docker Compose healthchecks
    and Prometheus/monitoring to confirm the service is responding."""
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "auth-service", "message": "Auth service is running"}


@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    db.refresh(user)
    return user


@app.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    # Deliberately identical error for "no such user" and "wrong password" —
    # revealing which one it was would let an attacker enumerate valid emails.
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )

    if not user or not verify_password(payload.password, user.password_hash):
        raise invalid_credentials

    token = create_access_token(user_id=str(user.id), role=user.role.value)
    return TokenResponse(access_token=token)


@app.get("/me", response_model=UserResponse)
def me(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Returns the current user's profile based on their JWT. Also serves
    as a convenient way for other services to validate a token by proxy,
    and for testing that authentication is working end-to-end."""
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user
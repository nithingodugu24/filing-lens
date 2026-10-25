"""Optional JWT authentication and tenant scoping. Empty secret keeps the local demo open."""

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import JWTError, jwt
from passlib.hash import bcrypt
from pydantic import BaseModel, Field
from sqlalchemy import event, select
from sqlalchemy.orm import Session, with_loader_criteria

from .config import get_settings
from .db import get_db
from .models import Annotation, ConversationHistory, Document, QueryRun, User
from .schemas import UserResponse, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["Auth"])
_attempts = defaultdict(deque)
_attempt_lock = Lock()


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=10, max_length=72)


class Registration(Credentials):
    full_name: str = Field(min_length=1, max_length=120)


def public_user(user):
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role}


def decode_token(token):
    settings = get_settings()
    if not settings.jwt_secret_key or len(settings.jwt_secret_key) < 32 or settings.jwt_algorithm != "HS256":
        raise HTTPException(503, "Set JWT_SECRET_KEY to at least 32 characters and JWT_ALGORITHM=HS256.")
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            issuer="filinglens",
            audience="filinglens-ui",
        )
        return claims["sub"]
    except (JWTError, KeyError):
        raise HTTPException(401, "Your session expired. Please sign in again.") from None


def current_user(db, token):
    user = db.get(User, decode_token(token))
    if not user or not user.is_active:
        raise HTTPException(401, "Please sign in again.")
    return user


def authenticate_request(db, request):
    settings = get_settings()
    if not settings.jwt_secret_key:
        return
    public = {
        "/api/health",
        "/api/ready",
        "/api/auth/config",
        "/api/auth/login",
        "/api/auth/register",
        "/api/docs",
        "/api/openapi.json",
        "/api/logo.svg",
        "/api/terms",
        "/docs",
    }
    if request.url.path in public or request.method == "OPTIONS":
        return
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Please sign in to continue.")
    user = current_user(db, token)
    db.info.update(user_id=user.id, role=user.role)
    request.state.user = user
    if request.url.path == "/api/demo" and user.role != "admin":
        raise HTTPException(403, "Only the administrator can load sample reports.")
    if request.method in {"POST", "PATCH", "DELETE", "PUT"} and user.role == "viewer":
        read_actions = {
            "/api/search",
            "/api/questions",
            "/api/compare",
            "/api/export/report",
            "/api/conversations",
            "/api/auth/refresh",
        }
        if "/annotations" in request.url.path or request.url.path.endswith(
            ("/analyze-sentiment", "/extract-entities")
        ):
            return
        if request.url.path not in read_actions:
            raise HTTPException(403, "An analyst or administrator account is needed for this action.")


@event.listens_for(Session, "do_orm_execute")
def scope_owned_records(execute_state):
    user_id = execute_state.session.info.get("user_id")
    if not user_id or execute_state.session.info.get("role") == "admin":
        return
    for model in (Document, Annotation, QueryRun, ConversationHistory):
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(model, model.user_id == user_id, include_aliases=True)
        )


def require_role(role):
    def dependency(request: Request, db: Session = Depends(get_db)):
        user = getattr(request.state, "user", None)
        if get_settings().jwt_secret_key and (user is None or user.role not in {role, "admin"}):
            raise HTTPException(403, "Your account cannot perform this action.")
        return user

    return dependency


def limit_auth(request):
    # Single-process development limiter. Use an edge/shared limiter for multi-instance deployment.
    key = request.client.host if request.client else "unknown"
    with _attempt_lock:
        now = time.monotonic()
        if len(_attempts) > 10000:
            for stale in [k for k, v in _attempts.items() if not v or v[-1] < now - 60]:
                del _attempts[stale]
        queue = _attempts[key]
        while queue and queue[0] < now - 60:
            queue.popleft()
        if len(queue) >= 20:
            raise HTTPException(429, "Too many sign-in attempts. Try again in a minute.")
        queue.append(now)


def token_response(user, started=None):
    s = get_settings()
    if len(s.jwt_secret_key) < 32 or s.jwt_algorithm != "HS256":
        raise HTTPException(503, "Configure a JWT secret of at least 32 characters before using accounts.")
    expires = datetime.now(timezone.utc) + timedelta(minutes=s.access_token_expire_minutes)
    started = started or datetime.now(timezone.utc).timestamp()
    if datetime.now(timezone.utc).timestamp() - started > 8 * 60 * 60:
        raise HTTPException(401, "Please sign in again to continue your session.")
    token = jwt.encode(
        {
            "sub": user.id,
            "exp": expires,
            "iat": datetime.now(timezone.utc),
            "iss": "filinglens",
            "aud": "filinglens-ui",
            "auth_time": started,
        },
        s.jwt_secret_key,
        algorithm="HS256",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires.isoformat(),
        "user": public_user(user),
    }


@router.get("/config", response_model=dict[str, bool])
def auth_config():
    return {"enabled": bool(get_settings().jwt_secret_key)}


@router.post("/register", status_code=201, response_model=TokenResponse)
def register(data: Registration, request: Request, db: Session = Depends(get_db)):
    if not get_settings().jwt_secret_key:
        raise HTTPException(409, "Accounts are disabled for this local demo.")
    limit_auth(request)
    if len(data.password.encode()) > 72:
        raise HTTPException(422, "Password must be at most 72 UTF-8 bytes.")
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text

        db.execute(text("SELECT pg_advisory_xact_lock(73521845)"))
    email = data.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account already exists with that email.")
    first = db.scalar(select(User.id).limit(1)) is None
    user = User(
        email=email,
        password_hash=bcrypt.hash(data.password),
        full_name=data.full_name.strip(),
        role="admin" if first else "analyst",
    )
    db.add(user)
    db.flush()
    if first:
        # Existing local-demo reports become the first administrator's documents.
        from sqlalchemy import update

        db.execute(update(Document).where(Document.user_id.is_(None)).values(user_id=user.id))
    response = token_response(user)
    db.commit()
    return response


@router.post("/login", response_model=TokenResponse)
def login(data: Credentials, request: Request, db: Session = Depends(get_db)):
    limit_auth(request)
    user = db.scalar(select(User).where(User.email == data.email.strip().lower()))
    if (
        not user
        or not user.is_active
        or len(data.password.encode()) > 72
        or not bcrypt.verify(data.password, user.password_hash)
    ):
        raise HTTPException(401, "Email or password is incorrect.")
    return token_response(user)


@router.get("/me", response_model=UserResponse)
def me(request: Request, db: Session = Depends(get_db)):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(401, "Accounts are disabled or you are not signed in.")
    return public_user(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: Request, db: Session = Depends(get_db)):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(401, "Please sign in again.")
    token = request.headers.get("authorization", "").split(" ", 1)[-1]
    s = get_settings()
    claims = jwt.decode(
        token, s.jwt_secret_key, algorithms=["HS256"], issuer="filinglens", audience="filinglens-ui"
    )
    return token_response(user, claims.get("auth_time", claims["iat"]))

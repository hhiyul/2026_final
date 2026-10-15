"""Shared MongoDB sessions. The browser receives only an HttpOnly opaque cookie."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from pwdlib import PasswordHash
from pymongo.errors import DuplicateKeyError

COOKIE_NAME = "wearly_session"
SESSION_SECONDS = 60 * 60 * 24 * 7
DEFAULT_ORIGINS = "http://localhost,http://localhost:80,http://localhost:3000,http://localhost:5173,http://localhost:8080,http://127.0.0.1,http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:8080"
ALLOWED_ORIGINS = [value.strip().rstrip("/") for value in os.getenv("FRONTEND_ORIGINS", DEFAULT_ORIGINS).split(",") if value.strip()]
COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Credentials(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("user_id")
    @classmethod
    def normalize_id(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("사용자 ID를 입력해 주세요.")
        return value


class AuthService:
    def __init__(self, users, sessions, garments=None):
        self.users = users
        self.sessions = sessions
        self.garments = garments
        self.passwords = PasswordHash.recommended()
        self.dummy_hash = self.passwords.hash(secrets.token_urlsafe(32))
        self.router = APIRouter()
        self.router.add_api_route("/users", self.register, methods=["POST"], status_code=201)
        self.router.add_api_route("/auth/login", self.login, methods=["POST"])
        self.router.add_api_route("/auth/logout", self.logout, methods=["POST"])
        self.router.add_api_route("/auth/me", self.me, methods=["GET"])

    def create_indexes(self):
        self.users.create_index("user_id", unique=True)
        # MongoDB TTL cleanup is asynchronous; current_user also checks expiry.
        self.sessions.create_index("expires_at", expireAfterSeconds=0)
        self.sessions.create_index("user_id")

    def verify_password(self, user_id, password):
        user = self.users.find_one({"user_id": user_id})
        try:
            valid = self.passwords.verify(password, user["password_hash"] if user else self.dummy_hash)
        except Exception:
            valid = False
        return bool(user and valid)

    def register(self, req: Credentials):
        if self.users.find_one({"user_id": req.user_id}, {"_id": 1}):
            raise HTTPException(409, "이미 사용 중인 아이디입니다.")
        # Old anonymous uploads must not become claimable by guessing their ID.
        if self.garments is not None and self.garments.find_one({"user_id": req.user_id}, {"_id": 1}):
            raise HTTPException(409, "기존 옷장 데이터가 있는 아이디입니다. 다른 아이디로 가입해 주세요.")
        try:
            self.users.insert_one({"user_id": req.user_id, "password_hash": self.passwords.hash(req.password), "created_at": datetime.now(timezone.utc).isoformat()})
        except DuplicateKeyError:
            raise HTTPException(409, "이미 사용 중인 아이디입니다.")
        return {"user_id": req.user_id, "message": "회원가입을 완료했습니다. 로그인해 주세요."}

    def login(self, req: Credentials, request: Request, response: Response):
        if not self.verify_password(req.user_id, req.password):
            raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")
        previous = request.cookies.get(COOKIE_NAME)
        if previous:
            self.sessions.delete_one({"_id": token_hash(previous)})
        token = secrets.token_urlsafe(32)
        self.sessions.insert_one({"_id": token_hash(token), "user_id": req.user_id, "expires_at": datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS)})
        response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True, secure=COOKIE_SECURE, samesite="lax", path="/")
        response.headers["Cache-Control"] = "no-store"
        return {"user_id": req.user_id}

    def current_user(self, request: Request):
        token = request.cookies.get(COOKIE_NAME)
        session = self.sessions.find_one({"_id": token_hash(token), "expires_at": {"$gt": datetime.now(timezone.utc)}}) if token else None
        if not session or not self.users.find_one({"user_id": session["user_id"]}, {"_id": 1}):
            raise HTTPException(401, "로그인이 필요하거나 로그인 시간이 만료되었습니다.")
        return session["user_id"]

    def me(self, request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return {"user_id": self.current_user(request)}

    def logout(self, request: Request, response: Response):
        token = request.cookies.get(COOKIE_NAME)
        if token:
            self.sessions.delete_one({"_id": token_hash(token)})
        response.delete_cookie(COOKIE_NAME, httponly=True, secure=COOKIE_SECURE, samesite="lax", path="/")
        response.headers["Cache-Control"] = "no-store"
        return {"message": "로그아웃했습니다."}

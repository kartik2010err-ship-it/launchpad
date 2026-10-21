from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core import rate_limit
from app.core.security import create_token, hash_password, verify_password
from app.db.session import get_db
from app.models.enums import Role
from app.models.project import User
from app.services import workspace_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _user_by_email(db: Session, email: str) -> User | None:
    # Compared case-insensitively so accounts created before emails were
    # normalized still match however the student types their address.
    return db.scalars(select(User).where(func.lower(User.email) == email)).first()


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    role: Role = Role.STUDENT
    school: str | None = None
    grade_level: int | None = None


    normalize_email = field_validator("email")(_normalize_email)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter your name.")
        return value.strip()


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)

    normalize_email = field_validator("email")(_normalize_email)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    role: Role


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    bucket = f"register:{rate_limit.client_ip(request)}"
    rate_limit.check(db, bucket)
    rate_limit.record(db, bucket)
    if _user_by_email(db, payload.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account already uses that email.")
    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        school=payload.school,
        grade_level=payload.grade_level,
    )
    db.add(user)
    db.flush()
    # Give every new account somewhere to work before they join anything.
    workspace_service.ensure_personal_workspace(db, user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_token(user.id), user_id=user.id, name=user.name, role=Role(user.role))


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    # Only failures are counted: per address, so one machine cannot spray many
    # accounts, and per account, so many machines cannot grind one password.
    buckets = (f"login-ip:{rate_limit.client_ip(request)}", f"login-email:{payload.email}")
    rate_limit.check(db, *buckets)
    user = _user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        rate_limit.record(db, *buckets)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    return TokenOut(access_token=create_token(user.id), user_id=user.id, name=user.name, role=Role(user.role))


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "school": user.school}

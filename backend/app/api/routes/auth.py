from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.security import create_token, hash_password, verify_password
from app.db.session import get_db
from app.models.enums import Role
from app.models.project import User
from app.services import workspace_service

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role = Role.STUDENT
    school: str | None = None
    grade_level: int | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    role: Role


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> TokenOut:
    if db.scalar(select(User).where(User.email == payload.email)):
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
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    return TokenOut(access_token=create_token(user.id), user_id=user.id, name=user.name, role=Role(user.role))


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "school": user.school}

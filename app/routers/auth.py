from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas.user import Token, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: Session = Depends(get_db)):
    """Registra un usuario nuevo."""
    email = data.email.lower()
    exists = db.scalar(
        select(User).where(or_(User.username == data.username, User.email == email))
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "El usuario o el correo ya están registrados")

    user = User(username=data.username, email=email, hashed_password=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Inicia sesión con usuario (o correo) y contraseña. Devuelve un JWT."""
    identifier = form.username.strip().lower()
    user = db.scalar(select(User).where(or_(User.username == identifier, User.email == identifier)))
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Devuelve el usuario autenticado."""
    return current_user

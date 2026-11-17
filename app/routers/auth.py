from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.rate_limit import client_ip, login_limiter, register_limiter
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas.user import Token, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

_DUPLICATE = "El usuario o el correo ya están registrados"


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, request: Request, db: Session = Depends(get_db)):
    """Registra un usuario nuevo (máx. 10 registros por hora por IP)."""
    register_limiter.hit(client_ip(request))
    email = data.email.lower()
    exists = db.scalar(
        select(User).where(or_(User.username == data.username, User.email == email))
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, _DUPLICATE)

    user = User(username=data.username, email=email, hashed_password=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # dos registros simultáneos con el mismo usuario/correo
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, _DUPLICATE)
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Inicia sesión con usuario (o correo) y contraseña. Devuelve un JWT.

    Limitado a 10 intentos por minuto por IP para frenar ataques de fuerza bruta.
    """
    login_limiter.hit(client_ip(request))
    identifier = form.username.strip().lower()[:255]
    user = db.scalar(select(User).where(or_(User.username == identifier, User.email == identifier)))
    # Siempre se ejecuta bcrypt para no revelar por tiempo si el usuario existe.
    hashed = user.hashed_password if user else DUMMY_PASSWORD_HASH
    password_ok = verify_password(form.password, hashed)
    if user is None or not password_ok:
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

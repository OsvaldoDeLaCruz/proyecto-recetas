from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import Ingredient, User
from app.schemas.ingredient import IngredientCreate, IngredientOut, IngredientUpdate

router = APIRouter(prefix="/api/ingredients", tags=["Ingredientes"])


def _get_owned(db: Session, ingredient_id: int, user: User) -> Ingredient:
    ingredient = db.get(Ingredient, ingredient_id)
    if ingredient is None or ingredient.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ingrediente no encontrado")
    return ingredient


def _name_taken(db: Session, user: User, name: str, exclude_id: int | None = None) -> bool:
    query = select(Ingredient.id).where(Ingredient.user_id == user.id, Ingredient.name == name)
    if exclude_id is not None:
        query = query.where(Ingredient.id != exclude_id)
    return db.scalar(query) is not None


@router.get("", response_model=list[IngredientOut])
def list_ingredients(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Lista el inventario del usuario ordenado alfabéticamente."""
    return db.scalars(
        select(Ingredient).where(Ingredient.user_id == user.id).order_by(Ingredient.name)
    ).all()


@router.post("", response_model=IngredientOut, status_code=status.HTTP_201_CREATED)
def create_ingredient(
    data: IngredientCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Agrega un ingrediente al inventario."""
    if _name_taken(db, user, data.name):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya tienes '{data.name}' en tu inventario")
    ingredient = Ingredient(user_id=user.id, **data.model_dump())
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return ingredient


@router.get("/{ingredient_id}", response_model=IngredientOut)
def get_ingredient(
    ingredient_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return _get_owned(db, ingredient_id, user)


@router.patch("/{ingredient_id}", response_model=IngredientOut)
def update_ingredient(
    ingredient_id: int,
    data: IngredientUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Actualiza nombre, cantidad o unidad de un ingrediente."""
    ingredient = _get_owned(db, ingredient_id, user)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        if changes["name"] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El nombre no puede ser nulo")
        if _name_taken(db, user, changes["name"], exclude_id=ingredient.id):
            raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe otro ingrediente con ese nombre")
    for field, value in changes.items():
        setattr(ingredient, field, value)
    db.commit()
    db.refresh(ingredient)
    return ingredient


@router.delete("/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ingredient(
    ingredient_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ingredient = _get_owned(db, ingredient_id, user)
    db.delete(ingredient)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

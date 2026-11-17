from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.core.rate_limit import generate_limiter
from app.core.security import get_current_user
from app.database import get_db
from app.models import Ingredient, Rating, Recipe, User
from app.schemas.recipe import (
    Difficulty,
    RatingIn,
    RatingOut,
    RecipeGenerateRequest,
    RecipeOut,
)
from app.services.llm_service import (
    LLMResponseError,
    LLMService,
    LLMUnavailableError,
    get_llm_service,
)

router = APIRouter(prefix="/api/recipes", tags=["Recetas"])


def to_out(recipe: Recipe) -> RecipeOut:
    return RecipeOut(
        id=recipe.id,
        title=recipe.title,
        ingredients=recipe.ingredients,
        steps=recipe.steps,
        prep_time_minutes=recipe.prep_time_minutes,
        difficulty=recipe.difficulty,
        servings=recipe.servings,
        llm_model=recipe.llm_model,
        created_at=recipe.created_at,
        rating=recipe.rating.score if recipe.rating else None,
    )


def _get_owned(db: Session, recipe_id: int, user: User) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None or recipe.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Receta no encontrada")
    return recipe


@router.post("/generate", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
def generate_recipe(
    data: RecipeGenerateRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm: LLMService = Depends(get_llm_service),
):
    """Genera una receta con el LLM a partir del inventario actual y la guarda en el historial."""
    data = data or RecipeGenerateRequest()
    query = (
        select(Ingredient)
        .where(Ingredient.user_id == user.id)
        .order_by(Ingredient.name)
        .limit(get_settings().max_ingredients_per_user)
    )
    if data.ingredient_ids:
        query = query.where(Ingredient.id.in_(data.ingredient_ids))
    inventory = db.scalars(query).all()

    if not inventory:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Tu inventario está vacío: agrega ingredientes antes de generar una receta",
        )

    # Máx. 5 generaciones por minuto por usuario (cada llamada al LLM tiene costo).
    generate_limiter.hit(f"user:{user.id}")

    try:
        generated = llm.generate_recipe(inventory, meal_type=data.meal_type, servings=data.servings)
    except LLMUnavailableError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El servicio de IA no está disponible en este momento. Intenta de nuevo.",
        ) from exc
    except LLMResponseError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "La IA devolvió una receta con formato inválido. Intenta de nuevo.",
        ) from exc

    recipe = Recipe(
        user_id=user.id,
        title=generated.nombre,
        ingredients=[i.model_dump() for i in generated.ingredientes],
        steps=generated.pasos,
        prep_time_minutes=generated.tiempo_estimado_min,
        difficulty=generated.dificultad,
        servings=data.servings,
        llm_model=llm.model,
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return to_out(recipe)


@router.get("", response_model=list[RecipeOut])
def list_recipes(
    difficulty: Difficulty | None = Query(default=None),
    min_rating: int | None = Query(default=None, ge=1, le=5),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Historial de recetas del usuario (más recientes primero)."""
    query = (
        select(Recipe)
        .where(Recipe.user_id == user.id)
        .options(selectinload(Recipe.rating))
        .order_by(Recipe.created_at.desc(), Recipe.id.desc())
    )
    if difficulty:
        query = query.where(Recipe.difficulty == difficulty)
    if min_rating:
        query = query.join(Rating).where(Rating.score >= min_rating)
    return [to_out(r) for r in db.scalars(query).all()]


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return to_out(_get_owned(db, recipe_id, user))


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(
    recipe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Elimina una receta del historial (y su calificación)."""
    recipe = _get_owned(db, recipe_id, user)
    db.delete(recipe)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{recipe_id}/rating", response_model=RatingOut)
def rate_recipe(
    recipe_id: int,
    data: RatingIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Califica una receta de 1 a 5 estrellas (crea o actualiza la calificación)."""
    recipe = _get_owned(db, recipe_id, user)
    if recipe.rating is None:
        recipe.rating = Rating(recipe_id=recipe.id, user_id=user.id, score=data.score, comment=data.comment)
    else:
        recipe.rating.score = data.score
        recipe.rating.comment = data.comment
    db.commit()
    db.refresh(recipe.rating)
    return recipe.rating

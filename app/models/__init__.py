"""Modelos ORM. Importarlos aquí registra las tablas en Base.metadata."""
from app.models.ingredient import Ingredient
from app.models.rating import Rating
from app.models.recipe import Recipe
from app.models.user import User

__all__ = ["User", "Ingredient", "Recipe", "Rating"]

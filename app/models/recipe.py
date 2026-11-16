from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import utcnow


class Recipe(Base):
    __tablename__ = "recetas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    # Lista de {"nombre": str, "cantidad": str}
    ingredients: Mapped[list[dict]] = mapped_column(JSON)
    # Lista de pasos en orden
    steps: Mapped[list[str]] = mapped_column(JSON)
    prep_time_minutes: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[str] = mapped_column(String(10))  # facil | media | dificil
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    user: Mapped["User"] = relationship(back_populates="recipes")  # noqa: F821
    rating: Mapped["Rating | None"] = relationship(  # noqa: F821
        back_populates="recipe", cascade="all, delete-orphan", uselist=False
    )

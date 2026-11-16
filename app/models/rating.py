from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import utcnow


class Rating(Base):
    __tablename__ = "calificaciones"
    __table_args__ = (CheckConstraint("score BETWEEN 1 AND 5", name="ck_calificacion_rango"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Una calificación por receta (cada receta pertenece a un único usuario).
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recetas.id", ondelete="CASCADE"), unique=True, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    recipe: Mapped["Recipe"] = relationship(back_populates="rating")  # noqa: F821

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


from datetime import datetime, timezone
from typing import Optional

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

db = SQLAlchemy()


class Recipe(db.Model):
    __tablename__ = 'recipes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey('transcription_jobs.job_id')) # TODO: Change this to be `external_recipe_id`
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    prep_time: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    cook_time: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    servings: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    image_path: Mapped[Optional[str]] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ingredients: Mapped[list['Ingredient']] = relationship(
        back_populates='recipe', cascade='all, delete-orphan', lazy=True
    )
    instructions: Mapped[list['Instruction']] = relationship(
        back_populates='recipe', cascade='all, delete-orphan', lazy=True
    )
    transcription_job: Mapped[Optional['TranscriptionJob']] = relationship(
        back_populates='recipe', uselist=False, lazy=True
    )

    def __init__(
        self,
        job_id: str,
        title: str,
        prep_time: Optional[str] = None,
        cook_time: Optional[str] = None,
        servings: Optional[str] = None,
        notes: Optional[str] = None,
        image_path: Optional[str] = None,
    ) -> None:
        self.job_id = job_id
        self.title = title
        self.prep_time = prep_time
        self.cook_time = cook_time
        self.servings = servings
        self.notes = notes
        self.image_path = image_path

    def __repr__(self) -> str:
        return f'<Recipe {self.title},{self.job_id}>'

class Ingredient(db.Model):
    __tablename__ = 'ingredients'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey('recipes.id'), nullable=False)
    item: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    unit: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    recipe: Mapped['Recipe'] = relationship(back_populates='ingredients', lazy=True)

    def __init__(
        self,
        item: str,
        quantity: Optional[str] = None,
        unit: Optional[str] = None,
        order: int = 0,
    ) -> None:
        self.item = item
        self.quantity = quantity
        self.unit = unit
        self.order = order

    def __repr__(self) -> str:
        return f'<Ingredient {self.item}>'

class Instruction(db.Model):
    __tablename__ = 'instructions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey('recipes.id'), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    recipe: Mapped['Recipe'] = relationship(back_populates='instructions', lazy=True)

    def __init__(
        self,
        step_number: int,
        description: str,
    ) -> None:
        self.step_number = step_number
        self.description = description

    def __repr__(self) -> str:
        return f'<Instruction {self.step_number}>'

class TranscriptionJob(db.Model):
    __tablename__ = 'transcription_jobs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False) # TODO: Rename to external_recipe_id
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default='pending', nullable=False
    )  # pending, processing, completed, failed
    last_status: Mapped[str] = mapped_column(String(255), default='Queued', nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)

    recipe: Mapped[Optional['Recipe']] = relationship(
        back_populates='transcription_job', lazy=True
    )

    def __init__(
        self,
        job_id: str,
        session_id: str,
        image_path: str,
        status: str = 'pending',
        last_status: str = 'Queued',
    ) -> None:
        self.job_id = job_id
        self.session_id = session_id
        self.image_path = image_path
        self.status = status
        self.last_status = last_status

    def __repr__(self) -> str:
        return f'<TranscriptionJob {self.job_id} - {self.status}>'

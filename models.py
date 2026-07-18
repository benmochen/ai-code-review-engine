from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo: Mapped[str] = mapped_column(String)
    pr_number: Mapped[int] = mapped_column(Integer)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"))

class Repository(Base):
    __tablename__ = "repositories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
from sqlalchemy.orm import DeclarativeBase

from app.db.base import Base


def test_base_is_sqlalchemy_declarative_base():
    assert issubclass(Base, DeclarativeBase)
    assert Base.metadata is not None

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy persistence models."""

    metadata = MetaData(naming_convention={"pk": "pk_%(table_name)s"})

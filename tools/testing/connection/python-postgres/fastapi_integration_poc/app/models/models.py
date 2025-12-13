from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class User(Base):
    """
    Example User model using SQLAlchemy 2.0 style.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)

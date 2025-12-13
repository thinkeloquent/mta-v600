from fastapi import APIRouter
from sqlalchemy import select, insert
from typing import List

from app.models.models import User
from app.schemas import UserCreate, User as UserSchema
from app.dependencies import SessionDep

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserSchema)
async def create_user(user: UserCreate, db: SessionDep):
    # SQLAlchemy 2.0 syntax: Construct object, add to session
    db_user = User(email=user.email, is_active=user.is_active)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.get("/", response_model=List[UserSchema])
async def read_users(db: SessionDep):
    # SQLAlchemy 2.0 syntax: select()
    result = await db.execute(select(User).limit(10))
    return result.scalars().all()

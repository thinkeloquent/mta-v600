from pydantic import BaseModel, ConfigDict, EmailStr

class UserBase(BaseModel):
    email: EmailStr
    is_active: bool = True

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    
    # Modern Pydantic V2 config (replaces orm_mode=True)
    model_config = ConfigDict(from_attributes=True)

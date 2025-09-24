from pydantic import BaseModel
from datetime import date

class PlayerCreate(BaseModel):
    host_id: bool
    nombre: str 
    avatar: str
    fechaNacimiento: date

from pydantic import BaseModel

class PlayerCreateRequest(BaseModel):
    nombre: str
    avatar: str
    fechaNacimiento: str

class PlayerResponse(BaseModel):
    id: int
    name: str
    avatar: str
    birthdate: str
    is_host: bool
    model_config = {"from_attributes": True}
    
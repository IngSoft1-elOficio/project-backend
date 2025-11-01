from pydantic import BaseModel

class AvailableSecret(BaseModel):
    """Representa un secreto revelado disponible para elegir."""
    id: int
    owner_id: int

# And then was one more (Step 1)
class OneMoreStartRequest(BaseModel):
    card_id: int # esto ya tiene el id del jugador al que hay q sacarle el secreto


class OneMoreStartResponse(BaseModel):
    action_id: int
    available_secrets: list[AvailableSecret]

# And then was one more (Step 2)
class OneMoreSecondRequest(BaseModel):
    action_id: int
    selected_secret_id: int

class OneMoreSecondResponse(BaseModel):
    allowed_players: list[int]

# And then was one more (step 3)
class OneMoreThirdRequest(BaseModel):
    action_id: int
    target_player_id: int

class OneMoreThirdResponse(BaseModel):
    success: bool
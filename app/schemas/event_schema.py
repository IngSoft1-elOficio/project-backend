from pydantic import BaseModel


# And then was one more (Step 1)
class OneMoreStartRequest(BaseModel):
    card_id: int # esto ya tiene el id del jugador al que hay q sacarle el secreto


class OneMoreStartResponse(BaseModel):
    action_id: int
    available_secrets: list[int]

# And then was one more (Step 2)
class OneMoreSecondRequest(BaseModel):
    action_id: int
    selected_secret_id: int

class OneMoreSecondResponse(BaseModel):
    action_id: int
    allowed_players: list[int]
from pydantic import BaseModel


# And then was one more (Step 1)
class SecretSummary(BaseModel):
    secret_id: int
    player_id: int
    
class OneMoreStartRequest(BaseModel):
    card_id: int # esto ya tiene el id del jugador al que hay q sacarle el secreto


class OneMoreStartResponse(BaseModel):
    action_id: int
    available_secrets: list[SecretSummary]

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
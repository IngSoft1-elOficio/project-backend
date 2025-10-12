# And then was one more (Step 1)
class OneMoreStartRequest(BaseModel):
    cardId: int # esto ya tiene el id del jugador al que hay q sacarle el secreto


class OneMoreStartResponse(BaseModel):
    actionId: int
    avaliable_secrets: list[int]


class AndThenOneMoreEffect(BaseModel):
    secretId: int
    originalOwnerId: int
    newOwnerId: int
    hidden: bool

class AndThenOneMoreResponse(BaseModel):
    success: bool
    effect: AndThenOneMoreEffect

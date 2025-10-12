# And then was one more

class AndThenOneMoreRequest(BaseModel):
    secretId: int
    targetPlayerId: int

class AndThenOneMoreEffect(BaseModel):
    secretId: int
    originalOwnerId: int
    newOwnerId: int
    hidden: bool

class AndThenOneMoreResponse(BaseModel):
    success: bool
    effect: AndThenOneMoreEffect

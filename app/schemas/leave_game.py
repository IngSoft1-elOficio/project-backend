from pydantic import BaseModel

class LeaveGameResponse(BaseModel):
    """Response schema for leave game endpoint"""
    status: str
    message: str
    is_host: bool
    
    model_config = {"from_attributes": True}


class GameCancelledEvent(BaseModel):
    """WebSocket event schema when host cancels game"""
    type: str = "game_cancelled"
    room_id: int
    timestamp: str


class PlayerLeftEvent(BaseModel):
    """WebSocket event schema when player leaves"""
    type: str = "player_left"
    player_id: int
    players_count: int
    timestamp: str
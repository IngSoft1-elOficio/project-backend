from pydantic import BaseModel
from typing import List, Optional, Union
from datetime import date
from app.db.models import CardType  

# ================================
# MAPEO DE STATUS
# ================================
STATUS_MAPPING = {
    "WAITING": "waiting",
    "INGAME": "in_game", 
    "FINISH": "finished"
}

# ================================
# SCHEMAS BÁSICOS
# ================================

class CardSummary(BaseModel):
    id: int
    name: str
    type: CardType
    img: str 

    model_config = {"from_attributes": True}

class PlayerView(BaseModel):
    id: int
    name: str
    avatar: str  
    birthdate: str  
    is_host: bool
    order: Optional[int] = None

    model_config = {"from_attributes": True}

class GameView(BaseModel):
    id: int
    name: str
    player_qty: int
    status: str  # "waiting" | "in_game" | "finished" 
    host_id: int

    model_config = {"from_attributes": True}

# ================================
# SCHEMAS DE ESTADO DEL JUEGO
# ================================

class DeckView(BaseModel):
    remaining: int  

class DiscardView(BaseModel):
    top: Optional[CardSummary] = None  
    count: int 

class HandView(BaseModel):
    player_id: int  
    cards: List[CardSummary]  

class SecretsView(BaseModel):
    player_id: int  
    cards: List[CardSummary]  

class TurnInfo(BaseModel):
    current_player_id: Optional[int]
    order: List[int]  
    can_act: bool  

# ================================
# SCHEMA PRINCIPAL
# ================================

class GameStateView(BaseModel):
    game: GameView
    players: List[PlayerView]
    deck: DeckView
    discard: DiscardView
    hand: Optional[HandView] = None  # solo para el jugador solicitante
    secrets: Optional[SecretsView] = None  # solo para el jugador solicitante
    turn: TurnInfo

    model_config = {"from_attributes": True}

# ================================
# SCHEMA DE ERRORES 
# ================================

class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None


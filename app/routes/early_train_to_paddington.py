from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import (
  Game, Room, CardsXGame, CardState, Player, ActionsPerTurn,
  ActionType, ActionResult, Turn, TurnStatus, Card, ActionName
)
from app.db.crud import get_room_by_id, get_player_by_id, get_game_by_id
from app.sockets.socket_service import get_websocket_service
from app.services.game_status_service import build_complete_game_state
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/game", tags=["Games"])

def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()

class CardInfo(BaseModel):
  cardId: int
  name: str
  type: str
  position: int | None = None
  previousPosition: int | None = None

class DiscardInfo(BaseModel):
  top: CardInfo
  count: int

class PlayerHandInfo(BaseModel):
  player_id: int
  discardedPositions: list[int] = []
  remainingCards: list[CardInfo] = [] 

class DeckInfo(BaseModel):
  remaining: int

class EarlyTrainResponse(BaseModel):
  success: bool
  eventCardDiscarded: CardInfo
  sourcePlayerHand: PlayerHandInfo
  deck: DeckInfo


@router.post("/{room_id}/event/early_train_to_paddington", response_model=EarlyTrainResponse ,status_code=200)
async def cards_off_the_table(
  room_id: int,
  actor_user_id: int = Header(..., alias="HTTP_USER_ID"),
  db: Session = Depends(get_db)
):
  try:
    room = get_room_by_id(db, room_id)
    if not room:
      raise HTTPException(status_code=404, detail="Room not found")
    
    game = get_game_by_id(db, room.id_game)
    if not game:
      raise HTTPException(status_code=404, detail="Game not found")
    
    # Validar turno
    if game.player_turn_id != actor_user_id:
      raise HTTPException(status_code=403, detail="Not your turn")
    

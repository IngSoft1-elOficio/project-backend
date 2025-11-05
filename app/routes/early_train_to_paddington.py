from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import (
  Game, Room, CardsXGame, CardState, Player, ActionsPerTurn,
  ActionType, ActionResult, Turn, TurnStatus, Card, ActionName
)
from app.db.crud import get_room_by_id, get_game_by_id, get_max_position_by_state
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
  discard: DiscardInfo
  deck: DeckInfo


@router.post("/{room_id}/early_train_to_paddington", response_model=EarlyTrainResponse ,status_code=200)
async def cards_off_the_table(
  room_id: int,
  actor_user_id: int = Header(..., alias="HTTP_USER_ID"),
  db: Session = Depends(get_db)
):

  print(f"==> Entró al endpoint Early train")
  print(f"room_id={room_id}, actor_user_id={actor_user_id}")

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
  
    actor = db.query(Player).filter(Player.id == actor_user_id, Player.id_room == room_id).first()
    if not actor:
      raise HTTPException(status_code=404, detail="Actor player not found")

    # Obtener el turno actual
    current_turn = db.query(Turn).filter(
      Turn.id_game == game.id,
      Turn.player_id == actor.id,
      Turn.status == TurnStatus.IN_PROGRESS
    ).first()
    if not current_turn:
      raise HTTPException(status_code=403, detail="No active turn found")
    
    # Busco la carta en la mano del jugador
    event_card = db.query(CardsXGame).join(Card).filter(
      CardsXGame.player_id == actor.id,
      CardsXGame.id_game == game.id,
      CardsXGame.is_in == CardState.HAND,
      Card.name == "Early train to paddington"
    ).first()
    if not event_card:
      raise HTTPException(status_code=404, detail="Card not found")
    
    # Busco las primeras 6 cartas del deck
    first_six = db.query(CardsXGame).filter(
      CardsXGame.id_game == game.id,
      CardsXGame.is_in == CardState.DECK
    ).order_by(
      CardsXGame.position.desc()
    ).limit(6).all()

    if not first_six:
      raise HTTPException(status_code=400, detail="Empty deck")

    # Elimino la carta del juego
    event_card.is_in = CardState.REMOVED
    event_card.player_id = None

    # Calcular siguiente posición en discard
    max_discard_position = db.query(CardsXGame.position).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DISCARD
    ).order_by(CardsXGame.position.desc()).first()
    next_discard_position = (max_discard_position[0] + 1) if max_discard_position else 1

    action_event = ActionsPerTurn(
      id_game=game.id,
      turn_id=current_turn.id,
      player_id=actor.id,
      action_type=ActionType.EVENT_CARD,
      action_name=ActionName.EARLY_TRAIN_TO_PADDINGTON,
      result=ActionResult.now(),
      selected_card_id=event_card.id,
    )
    db.add(action_event)
    db.flush()

    if first_six:
      parent_action = ActionsPerTurn(
        id_game=game.id,
        turn_id=current_turn.id,
        player_id=actor.id,
        action_type=ActionType.DISCARD,
        result=ActionResult.SUCCESS,
        action_time=datetime.now(),
        parent_action_id=action_event.id
      )
      db.add(parent_action)
      db.flush()

      for i, card in enumerate(first_six):
        prev_pos = card.position
        card.is_in = CardState.DISCARD
        card.player_id = None
        card.position = next_discard_position + 1 + i
        card.hidden = False

        db.add(ActionsPerTurn(
          id_game=game.id,
          turn_id=current_turn.id,
          player_id=actor.id,
          action_type=ActionType.DISCARD,
          result=ActionResult.SUCCESS,
          action_time=datetime.now(),
          selected_card_id=card.id,
          position_card_id=card.position,
          parent_action_id=parent_action.id
        ))

    db.commit()

    # Estado final
    top_discard = db.query(CardsXGame).filter(
      CardsXGame.id_game == game.id,
      CardsXGame.is_in == CardState.DISCARD
    ).order_by(CardsXGame.position.desc()).first()

    discard_count = db.query(CardsXGame).filter(
      CardsXGame.id_game == game.id,
      CardsXGame.is_in == CardState.DISCARD
    ).count()

    deck_remaining = db.query(CardsXGame).filter(
      CardsXGame.id_game == game.id,
      CardsXGame.is_in == CardState.DECK
    )

    response = EarlyTrainResponse(
      success=True,
      eventCardDsicarded=CardInfo(
        cardId=event_card.id,
        name=event_card.card_name if event_card.card else "Early train to paddington",
        type=event_card.card.type.value if event_card.card and event_card.card.type else "EVENT"
      ),
      sourcePlayerHand=PlayerHandInfo(player_id=actor.id),
      discard=DiscardInfo(
        top=CardInfo(
          cardId=top_discard.id,
          name=top_discard.card.name if top_discard.card else "Unknown",
          type=top_discard.card.type.value if top_discard.card and top_discard.card.type else "UNKNOWN"
        ),
        count=discard_count
      ),
      deck=DeckInfo(remaining=deck_remaining)
    )

    # Notificar estado actualizado
    game_state = build_complete_game_state(db, game.id)
    ws_service = get_websocket_service()
    await ws_service.notificar_estado_partida(
        room_id=room_id,
        jugador_que_actuo=actor.id,
        game_state=game_state
    )

    logger.info(f"Early train to paddington completado.")
    return response
    
  except HTTPException:
    raise
  except Exception as e:
    logger.error(f"Error en Early train to paddington: {e}", exc_info=True)
    db.rollback()
  raise HTTPException(status_code=500, detail=f"Error processing early train to paddington: {str(e)}")
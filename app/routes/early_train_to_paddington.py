from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import (
  Game, Room, CardsXGame, CardState, Player, ActionsPerTurn,
  ActionType, ActionResult, Turn, TurnStatus, Card, ActionName
)
from app.db.crud import get_room_by_id, get_game_by_id
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
  
class EarlyTrainRequest(BaseModel):
  card_id: int

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


@router.post("/{room_id}/early_train_to_paddington", response_model=EarlyTrainResponse, status_code=200)
async def early_train_to_paddington(
  room_id: int,
  request: EarlyTrainRequest,
  actor_user_id: int = Header(..., alias="http-user-id"),
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
  
    actor = db.query(Player).filter(
      Player.id == actor_user_id, 
      Player.id_room == room_id
    ).first()
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
    
    event_card = db.query(CardsXGame).join(Card).filter(
      CardsXGame.id == request.card_id,
      CardsXGame.player_id == actor.id,
      CardsXGame.id_game == game.id,
      CardsXGame.is_in == CardState.HAND,
      Card.name == "Early train to paddington"
    ).first()
    if not event_card:
      raise HTTPException(status_code=404, detail="Event card not found in hand")
    
    # Agarro las 6 del deck
    first_six = db.query(CardsXGame).filter(
      CardsXGame.id_game == game.id,
      CardsXGame.is_in == CardState.DECK
    ).order_by(
      CardsXGame.position.desc()
    ).limit(6).all()

    if not first_six:
      raise HTTPException(status_code=409, detail="Deck is empty - state changed concurrently")

    max_discard_position = db.query(CardsXGame.position).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DISCARD
    ).order_by(CardsXGame.position.desc()).first()
    next_discard_position = (max_discard_position[0] + 1) if max_discard_position else 1

    # Elimino la carta evento del juego
    event_card.is_in = CardState.REMOVED
    event_card.player_id = None
    event_card.position = 0

    action_event = ActionsPerTurn(
      id_game=game.id,
      turn_id=current_turn.id,
      player_id=actor.id,
      action_type=ActionType.EVENT_CARD,
      action_name=ActionName.EARLY_TRAIN_TO_PADDINGTON,
      result=ActionResult.SUCCESS,
      action_time=datetime.now(),
      selected_card_id=event_card.id,
    )
    db.add(action_event)
    db.flush()

    # muevo las cartas del deck al discard 
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
        card.is_in = CardState.DISCARD
        card.player_id = None
        card.position = next_discard_position + i
        card.hidden = False

        db.add(ActionsPerTurn(
          id_game=game.id,
          turn_id=current_turn.id,
          player_id=actor.id,
          action_type=ActionType.DISCARD,
          result=ActionResult.SUCCESS,
          action_time=datetime.now(),
          selected_card_id=card.id,
          parent_action_id=parent_action.id
        ))

    remaining_deck_cards = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DECK
    ).order_by(CardsXGame.position.desc()).all()

    for idx, card in enumerate(remaining_deck_cards, start=1):
        card.position = idx

    db.commit()

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
    ).count()

    response = EarlyTrainResponse(
      success=True,
      eventCardDiscarded=CardInfo(
        cardId=event_card.id,
        name=event_card.card.name if event_card.card else "Early train to paddington",
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

    ws_service = get_websocket_service()

    await ws_service.notificar_event_step_update(
        room_id=room_id,
        player_id=actor.id,
        event_type="early_train",
        step="finish",
        message=f"Jugador {actor.name} Early train to paddington, se mueven cartas al discard"
    )
    logger.info("Se emitió el evento event_step_update del robo del set")    

    game_state = build_complete_game_state(db, game.id)
    await ws_service.notificar_estado_partida(
        room_id=room_id,
        game_state=game_state,
        partida_finalizada=False
    )

    logger.info(f"Early train to paddington completado. Movidas cartas del deck al discard.")
    return response
    
  except HTTPException:
    raise
  except Exception as e:
    logger.error(f"Error en Early train to paddington: {e}", exc_info=True)
    db.rollback()
    raise HTTPException(status_code=500, detail=f"Error processing early train to paddington: {str(e)}")
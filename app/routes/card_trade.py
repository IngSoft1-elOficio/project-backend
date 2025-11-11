# app/routes/card_trade.py
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.services.game_status_service import build_complete_game_state
from pydantic import BaseModel
from app.db.crud import get_room_by_id, get_player_by_id, get_game_by_id
from app.db.models import (
    CardsXGame, CardState, ActionsPerTurn, ActionType, 
    ActionResult, ActionName, Turn, TurnStatus, Card, Room, Game, Player
)
from app.sockets.socket_service import get_websocket_service
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

class CardTradePlayRequest(BaseModel):
    own_card_id: int
    target_player_id: int

class CardTradeCompleteRequest(BaseModel):
    action_id: int
    own_card_id: int

class CardInfo(BaseModel):
    cardId: int
    name: str
    type: str
    playerId: int | None = None

class CardTradePlayResponse(BaseModel):
    success: bool
    action_id: int
    message: str
    requester_id: int
    target_id: int
    card_given: CardInfo


class CardTradeCompleteResponse(BaseModel):
    success: bool
    message: str
    player1_id: int
    player2_id: int
    card_exchanged_p1: CardInfo
    card_exchanged_p2: CardInfo

@router.post("/{room_id}/event/card-trade/play", response_model=CardTradePlayResponse, status_code=200)
async def card_trade_play(
    room_id: int,
    request: CardTradePlayRequest,
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

    actor = db.query(Player).filter(
       Player.id == actor_user_id,
       Player.id_room == room_id
    ).first()
    if not actor:
      raise HTTPException(status_code=404, detail="Actor not found")
    
    target_player = db.query(Player).filter(
       Player.id == request.target_player_id,
       Player.id_room == room_id
    ).first()
    if not target_player:
      raise HTTPException(status_code=403, detail="Target not found")
    
    if actor.id == target_player.id:
      raise HTTPException(status_code=400, detail="Cannot trade yourself")

    # Obtener el turno actual
    current_turn = db.query(Turn).filter(
      Turn.id_game == game.id,
      Turn.player_id == actor.id,
      Turn.status == TurnStatus.IN_PROGRESS
    ).first()
    if not current_turn:
      raise HTTPException(status_code=403, detail="No active turn found")
    
    # IMPORTANTE: Buscar la carta "Card Trade" en la mano del jugador
    # Esta es la carta del EVENTO que se está jugando
    card_trade_event = db.query(CardsXGame).join(Card).filter(
        CardsXGame.player_id == actor.id,
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.HAND,
        Card.name == "Card Trade",
        Card.type == "EVENT"
    ).first()
    
    if not card_trade_event:
        raise HTTPException(
            status_code=404, 
            detail="Card Trade event card not found in your hand"
        )
    
    # Validar que la carta a intercambiar está en la mano de P1
    # Y que NO sea la carta "Card Trade" misma
    p1_card = db.query(CardsXGame).filter(
        CardsXGame.id == request.own_card_id,
        CardsXGame.player_id == actor.id,
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.HAND
    ).first()
    if not p1_card:
      raise HTTPException(status_code=404, detail="Card not found in your hand")
    
    # Validar que no intente intercambiar la carta "Card Trade" misma
    if p1_card.id == card_trade_event.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot trade the Card Trade event card itself"
        )

    # Validar que el target tiene al menos una carta
    target_has_cards = db.query(CardsXGame).filter(
        CardsXGame.player_id == target_player.id,
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.HAND
    ).count() > 0
    
    if not target_has_cards:
        raise HTTPException(
            status_code=400,
            detail="Target player has no cards to trade"
        )

    # DESCARTAR LA CARTA "CARD TRADE" 
    # Obtener la posición máxima en el descarte
    max_discard_pos = db.query(CardsXGame.position).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DISCARD
    ).order_by(CardsXGame.position.desc()).first()
    
    next_discard_position = (max_discard_pos[0] + 1) if max_discard_pos else 1
    
    # Mover la carta "Card Trade" al descarte
    card_trade_event.is_in = CardState.DISCARD
    card_trade_event.position = next_discard_position
    card_trade_event.hidden = False
    card_trade_event.player_id = None  # Ya no pertenece a ningún jugador

    # Crear acción padre (PENDING hasta que P2 complete)
    action = ActionsPerTurn(
        id_game=game.id,
        turn_id=current_turn.id,
        player_id=actor.id,
        action_type=ActionType.CARD_EXCHANGE,
        action_name=ActionName.CARD_TRADE,
        result=ActionResult.PENDING,
        action_time=datetime.now(),
        player_source=actor.id,
        player_target=target_player.id,
        card_given_id=p1_card.id,  # Carta que P1 da
        selected_card_id=card_trade_event.id,  # La carta evento que se jugó
        # card_received_id se llenará cuando P2 seleccione su carta
    )
    db.add(action)
    db.flush()
    
    db.commit()

    response = CardTradePlayResponse(
      success=True,
      action_id=action.id,
      message=f"Waiting for {target_player.name} to select a card",
      requester_id=actor.id,
      target_id=target_player.id,
      card_given=CardInfo(
          cardId=p1_card.id,
          name=p1_card.card.name if p1_card.card else "Unknown",
          type=p1_card.card.type.value if p1_card.card else "UNKNOWN",
          playerId=actor.id
      )
    )
      
    # Emitir WebSocket a P2 para que seleccione su carta
    ws_service = get_websocket_service()
    await ws_service.notificar_card_trade_select_own_card(
      room_id=room_id,
      action_id=action.id,
      requester_id=actor.id,
      requester_name=actor.name,
      target_id=target_player.id
    )

    logger.info(
        f"Card Trade initiated by player {actor.id} targeting {target_player.id}. "
        f"Action ID: {action.id}. Card Trade event discarded to position {next_discard_position}"
      )
      
    return response
  
  except HTTPException:
    raise
  except Exception as e:
    logger.error(f"Error in card_trade_play: {e}", exc_info=True)
    db.rollback()
    raise HTTPException(status_code=500, detail=f"Error processing card trade: {str(e)}")


@router.post("/{room_id}/event/card-trade/complete", response_model=CardTradeCompleteResponse, status_code=200)
async def card_trade_complete(
   room_id: int,
   request: CardTradeCompleteRequest,
   actor_user_id: int = Header(..., alias="HTTP_USER_ID"),
   db: Session = Depends(get_db)
):
  try:
    # Validar room y game
    room = get_room_by_id(db, room_id)
    if not room:
      raise HTTPException(status_code=404, detail="Room not found")
    
    game = get_game_by_id(db, room.id_game)
    if not game:
      raise HTTPException(status_code=404, detail="Game not found")
    
    # Obtener la acción
    action = db.query(ActionsPerTurn).filter(
      ActionsPerTurn.id == request.action_id,
      ActionsPerTurn.id_game == game.id,
      ActionsPerTurn.action_type == ActionType.CARD_EXCHANGE,
      ActionsPerTurn.action_name == ActionName.CARD_TRADE,
      ActionsPerTurn.result == ActionResult.PENDING
    ).first()
    
    if not action:
      raise HTTPException(status_code=404, detail="Card trade action not found or already completed")
    
    # Validar que el actor es el target de la acción
    if action.player_target != actor_user_id:
      raise HTTPException(status_code=403, detail="You are not the target of this card trade")
    
    # Obtener jugadores
    p1 = db.query(Player).filter(Player.id == action.player_source).first()
    p2 = db.query(Player).filter(Player.id == actor_user_id).first()
    
    if not p1 or not p2:
      raise HTTPException(status_code=404, detail="Players not found")
    
    # Obtener la carta que P1 dio (ya almacenada en card_given_id)
    p1_card = db.query(CardsXGame).filter(
      CardsXGame.id == action.card_given_id,
      CardsXGame.id_game == game.id
    ).first()
    
    if not p1_card:
      raise HTTPException(status_code=404, detail="P1 card not found - state changed")
    
    # Validar que la carta de P1 todavía está en su mano
    if p1_card.player_id != p1.id or p1_card.is_in != CardState.HAND:
        raise HTTPException(status_code=409, detail="P1 card is no longer available for trade")
    
    # Obtener la carta que P2 seleccionó
    p2_card = db.query(CardsXGame).filter(
      CardsXGame.id == request.own_card_id,
      CardsXGame.player_id == p2.id,
      CardsXGame.id_game == game.id,
      CardsXGame.is_in == CardState.HAND
    ).first()
    
    if not p2_card:
      raise HTTPException(status_code=404, detail="Card not found in your hand")
    
    # Intercambiar las cartas
    temp_p1_id = p1.id
    temp_p2_id = p2.id

    # Intercambiar players_ids
    p1_card.player_id = temp_p2_id
    p2_card.player_id = temp_p1_id

    # Actualizar la acción con la carta recibida y marcar como SUCCESS
    action.card_received_id = p2_card.id
    action.result = ActionResult.SUCCESS
    action.action_time_end = datetime.now()
    
    db.commit()

    # Preparar respuesta
    response = CardTradeCompleteResponse(
      success=True,
      message=f"Card trade completed between {p1.name} and {p2.name}",
      player1_id=p1.id,
      player2_id=p2.id,
      card_exchanged_p1=CardInfo(
        cardId=p1_card.id,
        name=p1_card.card.name if p1_card.card else "Unknown",
        type=p1_card.card.type.value if p1_card.card else "UNKNOWN",
        playerId=temp_p2_id  # Ahora pertenece a P2
      ),
      card_exchanged_p2=CardInfo(
        cardId=p2_card.id,
        name=p2_card.card.name if p2_card.card else "Unknown",
        type=p2_card.card.type.value if p2_card.card else "UNKNOWN",
        playerId=temp_p1_id 
      )
    )
    
    ws_service = get_websocket_service()
    await ws_service.notificar_card_trade_complete(
        room_id=room_id,
        player1_id=p1.id,
        player1_name=p1.name,
        player2_id=p2.id,
        player2_name=p2.name,
        message=f"Card trade completed between {p1.name} and {p2.name}"
    )
    
    # Actualizar el estado completo del juego para todos
    game_state = build_complete_game_state(db, game.id)
    await ws_service.notificar_estado_partida(
        room_id=room_id,
        game_state=game_state,
        partida_finalizada=False
    )
    
    logger.info(
        f"Card Trade completed. Action ID: {action.id}. "
        f"P1 ({p1.id}) card {p1_card.id} <-> P2 ({p2.id}) card {p2_card.id}"
    )
    
    return response
    
  except HTTPException:
    raise
  except Exception as e:
    logger.error(f"Error in card_trade_complete: {e}", exc_info=True)
    db.rollback()
    raise HTTPException(status_code=500, detail=f"Error completing card trade: {str(e)}")
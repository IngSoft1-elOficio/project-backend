# app/routes/another_victim.py
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import (
    Game, Room, CardsXGame, CardState, Player, ActionsPerTurn, 
    ActionType, ActionResult, Turn, TurnStatus, Card, ActionName
)
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

class VictimRequest(BaseModel):
    originalOwnerId: int
    setPosition: int

class CardSummary(BaseModel):
    cardId: int
    name: str
    type: str

class TransferredSet(BaseModel):
    position: int
    cards: list[CardSummary]
    newOwnerId: int
    originalOwnerId: int

class VictimResponse(BaseModel):
    success: bool
    transferredSet: TransferredSet

@router.post("/{room_id}/event/another-victim", response_model=VictimResponse, status_code=200)
async def another_victim(
    room_id: int,
    request: VictimRequest,
    actor_user_id: int = Header(..., alias="HTTP_USER_ID"),
    db: Session = Depends(get_db)
):
    """
    Endpoint para robar un set de detective de otro jugador.
    Registra las acciones según el flujo definido en actions-turn-flow.md
    
    Args:
        room_id: ID de la sala
        request: Datos del robo (originalOwnerId, setPosition)
        actor_user_id: ID del jugador que roba (header)
    
    Returns:
        VictimResponse con información del set transferido
    """
    
    logger.info(f"POST /game/{room_id}/event/another-victim received")
    logger.info(f"Request: originalOwnerId={request.originalOwnerId}, setPosition={request.setPosition}")
    logger.info(f"Actor: {actor_user_id}")
    
    try:
        # Busco la sala
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        # Busco el juego
        game = db.query(Game).filter(Game.id == room.id_game).first()
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )

        actor = db.query(Player).filter(
            Player.id == actor_user_id,
            Player.id_room == room_id
        ).first()
        if not actor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Actor player not found"
            )
        
        # chequeo si es el turno del jugador
        if game.player_turn_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not your turn"
            )
        
        current_turn = db.query(Turn).filter(
            Turn.id_game == game.id,
            Turn.player_id == actor.id,
            Turn.status == TurnStatus.IN_PROGRESS
        ).first()
        
        if not current_turn:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No active turn found"
            )
        
        victim = db.query(Player).filter(
            Player.id == request.originalOwnerId,
            Player.id_room == room_id
        ).first()
        if not victim:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target player not found"
            )

        # Chequeo que no pueda robarse a su mismo
        if actor.id == victim.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot steal from yourself"
            )
        
        # Busco el set 
        victim_set_cards = db.query(CardsXGame).filter(
            CardsXGame.player_id == victim.id,
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.DETECTIVE_SET,
            CardsXGame.position == request.setPosition
        ).all()

        # chequeo que el set exista
        if not victim_set_cards:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No detective set found at position {request.setPosition} for player {request.originalOwnerId}"
            )
        
        # valido que el set es válido
        if len(victim_set_cards) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid detective set: must have at least 2 cards"
            )

        # descarto la another victim
        another_victim_card = db.query(CardsXGame).join(Card).filter(
            CardsXGame.player_id == actor.id,
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.HAND,
            Card.id == 13
        ).first()

        if another_victim_card:
            max_discard_position = db.query(CardsXGame.position).filter(
                CardsXGame.id_game == game.id,
                CardsXGame.is_in == CardState.DISCARD
            ).order_by(CardsXGame.position.desc()).first()
            
            next_discard_position = (max_discard_position[0] + 1) if max_discard_position else 1
            
            another_victim_card.is_in = CardState.DISCARD
            another_victim_card.position = next_discard_position
            another_victim_card.hidden = False
            another_victim_card.player_id = None
            
        
        # evento another victim
        action_event = ActionsPerTurn(
            id_game=game.id,
            turn_id=current_turn.id,
            player_id=actor.id,
            action_name="Another Victim",
            action_type=ActionType.EVENT_CARD,
            result=ActionResult.SUCCESS,
            action_time=datetime.now(),
            selected_card_id=another_victim_card.id if another_victim_card else None,
            player_target=victim.id,
            selected_set_id=request.setPosition
        )
        db.add(action_event)
        db.flush()
                
        # accion robar set
        action_steal = ActionsPerTurn(
            id_game=game.id,
            turn_id=current_turn.id,
            player_id=actor.id,
            action_type=ActionType.STEAL_SET,
            result=ActionResult.SUCCESS,
            action_time=datetime.now(),
            player_source=victim.id,
            player_target=actor.id,
            selected_set_id=request.setPosition,
            parent_action_id=action_event.id
        )
        db.add(action_steal)
        db.flush()
        
        
        # transfiero el set al actor
        for idx, card in enumerate(victim_set_cards):
            card.player_id = actor.id
            
            action_move = ActionsPerTurn(
                id_game=game.id,
                turn_id=current_turn.id,
                player_id=actor.id,
                action_type=ActionType.MOVE_CARD,
                result=ActionResult.SUCCESS,
                action_time=datetime.now(),
                selected_card_id=card.id,
                parent_action_id=action_steal.id
            )
            db.add(action_move)
        
        db.commit()
        
        transferred_cards = [
            CardSummary(
                cardId=card.id,
                name=card.card.name if card.card else "Unknown",
                type=card.card.type.value if card.card and card.card.type else "UNKNOWN"
            )
            for card in victim_set_cards
        ]
        
        response = VictimResponse(
            success=True,
            transferredSet=TransferredSet(
                position=request.setPosition,
                cards=transferred_cards,
                newOwnerId=actor.id,
                originalOwnerId=victim.id
            )
        )
    
        ws_service = get_websocket_service()
        

        await ws_service.notificar_event_step_update(
            room_id=room_id,
            player_id=actor.id,
            event_type="another_victim",
            step="set_stolen",
            message=f"El jugador {actor.name} robo un set de {victim.name}",
            data={
                "fromPlayerId": victim.id,
                "fromPlayerName": victim.name,
                "toPlayerId": actor.id,
                "toPlayerName": actor.name,
                "setPosition": request.setPosition,
                "cardCount": len(victim_set_cards),
                "transferredSet": {
                    "position": request.setPosition,
                    "cards": [
                        {
                            "cardId": c.cardId,
                            "name": c.name,
                            "type": c.type
                        } for c in transferred_cards
                    ],
                    "newOwnerId": actor.id,
                    "originalOwnerId": victim.id
                }
            }
        )
        logger.info(f"se emitio el evento")
        
        # notificar fin de accion
        await ws_service.notificar_event_action_complete(
            room_id=room_id,
            player_id=actor.id,
            event_type="another_victim"
        )
        logger.info(f"se emitio fin de accion")
        
        game_state = build_complete_game_state(db, game.id)
        
        await ws_service.notificar_estado_publico(
            room_id=room_id,
            game_state=game_state
        )
        
        await ws_service.notificar_estados_privados(
            room_id=room_id,
            estados_privados=game_state.get("estados_privados", {})
        )

        return response
        
    except HTTPException:
        raise 
    except Exception as e:
        logger.error(f"Error in another_victim: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error transferring detective set: {str(e)}"
        )
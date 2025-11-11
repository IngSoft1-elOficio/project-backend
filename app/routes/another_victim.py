# app/routes/another_victim.py
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import (
    Game, Room, CardsXGame, CardState, Player, ActionsPerTurn, 
    ActionType, ActionResult, Turn, TurnStatus, Card, ActionName
)
from app.schemas.detective_set_schema import SetType, NextAction
from app.sockets.socket_service import get_websocket_service
from app.services.game_status_service import build_complete_game_state
from app.services.detective_set_service import DetectiveSetService
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
    actionId: int  
    nextAction: NextAction 

@router.post("/{room_id}/event/another-victim", response_model=VictimResponse, status_code=200)
async def another_victim(
    room_id: int,
    request: VictimRequest,
    actor_user_id: int = Header(..., alias="http-user-id"),
    db: Session = Depends(get_db)
):
    """
    Endpoint para robar un set de detective de otro jugador.
    Registra las acciones según el flujo definido en actions-turn-flow.md
    Luego replica el efecto del set robado.
    
    Args:
        room_id: ID de la sala
        request: Datos del robo (originalOwnerId, setPosition)
        actor_user_id: ID del jugador que roba (header)
    
    Returns:
        VictimResponse con información del set transferido, actionId y la siguiente acción
    """

    print(f"owner: {request.originalOwnerId} postiion: {request.setPosition}")
    
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

        # Chequeo que no pueda robarse a si mismo
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
            Card.name == "Another Victim"
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
            
        # CALCULAR NUEVA POSICIÓN PARA EL SET ROBADO
        max_actor_set_position = db.query(CardsXGame.position).filter(
            CardsXGame.player_id == actor.id,
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.DETECTIVE_SET
        ).order_by(CardsXGame.position.desc()).first()
        
        new_set_position = (max_actor_set_position[0] + 1) if max_actor_set_position else 1
        
        logger.info(f"Set va a ser movido de posicion {request.setPosition} a {new_set_position}")
        
        # evento another victim
        action_event = ActionsPerTurn(
            id_game=game.id,
            turn_id=current_turn.id,
            player_id=actor.id,
            action_name=ActionName.ANOTHER_VICTIM,
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
            selected_set_id=new_set_position,
            parent_action_id=action_event.id
        )
        db.add(action_steal)
        db.flush()
        
        # Mover cartas al nuevo owner y posición
        for card in victim_set_cards:
            card.player_id = actor.id
            card.position = new_set_position
            
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
        
        db.flush()
        
        transferred_cards = [
            CardSummary(
                cardId=card.id,
                name=card.card.name if card.card else "Unknown",
                type=card.card.type.value if card.card and card.card.type else "UNKNOWN"
            )
            for card in victim_set_cards
        ]

        # Determinar el tipo de set robado y si tiene wildcard
        set_type, has_wildcard = _determine_stolen_set_type(victim_set_cards)
        
        logger.info(f"Tipo de set robado: {set_type.value}, tiene wildcard: {has_wildcard}")
        
        # Crear acción de detective set y determinar siguiente acción
        detective_service = DetectiveSetService(db)
        
        # Crear la acción DETECTIVE_SET con estado PENDING
        detective_action = detective_service._create_detective_action(
            game_id=game.id,
            turn_id=current_turn.id,
            player_id=actor.id,
            set_type=set_type
        )
        
        # El DETECTIVE_SET es hijo del STEAL_SET
        detective_action.parent_action_id = action_steal.id
        db.flush()
        
        logger.info(f"Crear detective actiion con id: {detective_action.id}")
    
        # Determinar la siguiente acción requerida según el tipo de set
        next_action = detective_service._determine_next_action(
            set_type=set_type,
            has_wildcard=has_wildcard,
            game_id=game.id,
            owner_id=actor.id
        )
        
        logger.info(f"Next action type: {next_action.type.value}")
        logger.info(f"Allowed players: {next_action.allowedPlayers}")
        
        db.commit()
        
        # Construir response
        response = VictimResponse(
            success=True,
            transferredSet=TransferredSet(
                position=new_set_position,
                cards=transferred_cards,
                newOwnerId=actor.id,
                originalOwnerId=victim.id
            ),
            actionId=detective_action.id,  # Include the detective action ID
            nextAction=next_action  # Direct NextAction object
        )
    
        ws_service = get_websocket_service()
        
        # Notificar que el set fue robado
        await ws_service.notificar_event_step_update(
            room_id=room_id,
            player_id=actor.id,
            event_type="another_victim",
            step="set_stolen",
            message=f"El jugador {actor.name} robó un set de {victim.name}",
            data={
                "fromPlayerId": victim.id,
                "fromPlayerName": victim.name,
                "toPlayerId": actor.id,
                "toPlayerName": actor.name,
                "originalSetPosition": request.setPosition,
                "newSetPosition": new_set_position,
                "cardCount": len(victim_set_cards),
                "transferredSet": {
                    "position": new_set_position,
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
        logger.info("Se emitió el evento event_step_update del robo del set")
        
        # Notificar que la acción de detective comenzó
        await ws_service.notificar_detective_action_started(
            room_id=room_id,
            player_id=actor.id,
            set_type=set_type.value
        )
        logger.info("Se emitió detective_action_started")
        
        # Obtener y notificar estado completo del juego
        game_state = build_complete_game_state(db, game.id)
        
        await ws_service.notificar_estado_publico(
            room_id=room_id,
            game_state=game_state
        )
        
        await ws_service.notificar_estados_privados(
            room_id=room_id,
            estados_privados=game_state.get("estados_privados", {})
        )

        logger.info(f"Another Victim completado. ActionId: {detective_action.id}, NextAction: {next_action.type.value}")
                         
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


def _determine_stolen_set_type(cards: list[CardsXGame]) -> tuple[SetType, bool]:
    """
    Determina el tipo de set y si contiene wildcard basándose en las cartas.
    
    Args:
        cards: Lista de CardsXGame del set robado
        
    Returns:
        Tuple de (SetType, has_wildcard)
    """
    HARLEY_QUIN_ID = 4
    TOMMY_BERESFORD_ID = 8
    TUPPENCE_BERESFORD_ID = 10
    
    card_ids = [card.id_card for card in cards]
    has_wildcard = HARLEY_QUIN_ID in card_ids
    
    # Contar cartas por tipo (excluyendo wildcard)
    non_wildcard = [cid for cid in card_ids if cid != HARLEY_QUIN_ID]
    
    # Mapeo inverso de ID a SetType
    id_to_set_type = {
        11: SetType.POIROT,
        6: SetType.MARPLE,
        12: SetType.SATTERTHWAITE,
        7: SetType.PYNE,
        9: SetType.EILEENBRENT,
    }
    
    # Verificar Beresford primero (caso especial)
    tommy_count = card_ids.count(TOMMY_BERESFORD_ID)
    tuppence_count = card_ids.count(TUPPENCE_BERESFORD_ID)
    
    if tommy_count > 0 or tuppence_count > 0:
        return SetType.BERESFORD, has_wildcard
    
    # Para otros sets, buscar el tipo más común
    if non_wildcard:
        most_common_id = max(set(non_wildcard), key=non_wildcard.count)
        if most_common_id in id_to_set_type:
            return id_to_set_type[most_common_id], has_wildcard
    
    # Fallback (no debería llegar aquí si la validación previa fue correcta)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Could not determine set type from stolen cards"
    )
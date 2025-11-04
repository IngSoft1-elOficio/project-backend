# app/routes/cards_off_the_table.py
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
from app.services.game_service import actualizar_turno, procesar_ultima_carta
from app.services.take_deck import robar_cartas_del_mazo
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

class TargetRequest(BaseModel):
    targetPlayerId: int

class CardInfo(BaseModel):
    cardId: int
    name: str
    type: str
    position: int | None = None
    previousPosition: int | None = None

class PlayerHandInfo(BaseModel):
    player_id: int
    drawnCard: CardInfo | None = None
    drawnCards: list[CardInfo] = []
    discardedPositions: list[int] = []
    remainingCards: list[CardInfo] = []

class DiscardInfo(BaseModel):
    top: CardInfo
    count: int

class DeckInfo(BaseModel):
    remaining: int

class CardsOffTableResponse(BaseModel):
    success: bool
    eventCardDiscarded: CardInfo
    discardedNSFCards: list[CardInfo]
    sourcePlayerHand: PlayerHandInfo
    targetPlayerHand: PlayerHandInfo
    discard: DiscardInfo
    deck: DeckInfo

@router.post("/{room_id}/event/cards-off-table", response_model=CardsOffTableResponse, status_code=200)
async def cards_off_the_table(
    room_id: int,
    request: TargetRequest,
    actor_user_id: int = Header(..., alias="HTTP_USER_ID"),
    db: Session = Depends(get_db)
):
    """
    Endpoint para forzar a un jugador a descartar todas sus cartas "Not so fast".
    Esta acción NO puede ser cancelada por NSF.
    
    Args:
        room_id: ID de la sala
        request: Datos del objetivo (targetPlayerId)
        actor_user_id: ID del jugador que usa la carta (header)
    
    Returns:
        CardsOffTableResponse con información detallada de la acción
    """
    
    logger.info(f"POST /api/game/{room_id}/event/cards-off-table received")
    logger.info(f"Request: targetPlayerId={request.targetPlayerId}, actor={actor_user_id}")
    
    try:
        # Buscar sala y juego
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        game = db.query(Game).filter(Game.id == room.id_game).first()
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )
        
        # Validar que es el turno del jugador
        if game.player_turn_id != actor_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not your turn"
            )

        # Obtener jugadores
        actor = db.query(Player).filter(
            Player.id == actor_user_id,
            Player.id_room == room_id
        ).first()
        if not actor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Actor player not found"
            )
        
        target = db.query(Player).filter(
            Player.id == request.targetPlayerId,
            Player.id_room == room_id
        ).first()
        if not target:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid target player"
            )

        # Obtener turno actual
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

        # Buscar la carta "Cards Off the Table" en la mano del actor
        # Primero intentamos con el ID de la carta (más eficiente)
        # Si no conoces el ID exacto, usa el join con Card
        event_card = db.query(CardsXGame).filter(
            CardsXGame.player_id == actor.id,
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.HAND,
            CardsXGame.id_card == 25  # ID de "Cards Off the Table"
        ).first()

        if not event_card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cards Off the Table card not found in hand"
            )

        # Buscar todas las cartas NSF en la mano del objetivo
        target_nsf_cards = db.query(CardsXGame).filter(
            CardsXGame.player_id == target.id,
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.HAND,
            CardsXGame.id_card == 13  # NSF card ID
        ).all()

        # Guardar posiciones anteriores antes de modificar
        nsf_previous_positions = {card.id: card.position for card in target_nsf_cards}

        # Calcular siguiente posición en discard pile
        max_discard_position = db.query(CardsXGame.position).filter(
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.DISCARD
        ).order_by(CardsXGame.position.desc()).first()
        
        next_discard_position = (max_discard_position[0] + 1) if max_discard_position else 1
        
        # Descartar la carta de evento
        event_card.is_in = CardState.DISCARD
        event_card.position = next_discard_position
        event_card.hidden = False
        event_card.player_id = None
        
        # Action 1: Jugar evento Cards Off the Table
        action_event = ActionsPerTurn(
            id_game=game.id,
            turn_id=current_turn.id,
            player_id=actor.id,
            action_name=ActionName.CARDS_OFF_THE_TABLE,
            action_type=ActionType.EVENT_CARD,
            result=ActionResult.SUCCESS,
            action_time=datetime.now(),
            selected_card_id=event_card.id,
            player_target=target.id
        )
        db.add(action_event)
        db.flush()
        
        logger.info(f"Created event action: id={action_event.id}")
        
        discarded_nsf_info = []
        
        # Procesar NSF cards si existen
        if len(target_nsf_cards) > 0:
            # Action 2 (PADRE): Descartar todas las NSF (acción forzada)
            action_discard_parent = ActionsPerTurn(
                id_game=game.id,
                turn_id=current_turn.id,
                player_id=target.id,  # La víctima descarta
                action_type=ActionType.DISCARD,
                result=ActionResult.SUCCESS,
                action_time=datetime.now(),
                parent_action_id=action_event.id
            )
            db.add(action_discard_parent)
            db.flush()
            
            logger.info(f"Created discard parent action: id={action_discard_parent.id}")
            
            # Descartar todas las cartas NSF
            for i, card in enumerate(target_nsf_cards):
                prev_pos = card.position
                card.is_in = CardState.DISCARD
                card.player_id = None
                card.position = next_discard_position + 1 + i
                card.hidden = False
                
                discarded_nsf_info.append(CardInfo(
                    cardId=card.id,
                    name=card.card.name if card.card else "Not so fast",
                    type=card.card.type.value if card.card and card.card.type else "INSTANT",
                    previousPosition=prev_pos
                ))
                
                # Action 3-N (HIJAS): Cada NSF descartada
                action_discard_card = ActionsPerTurn(
                    id_game=game.id,
                    turn_id=current_turn.id,
                    player_id=target.id,
                    action_type=ActionType.DISCARD,
                    result=ActionResult.SUCCESS,
                    action_time=datetime.now(),
                    selected_card_id=card.id,
                    position_card=card.position,
                    parent_action_id=action_discard_parent.id
                )
                db.add(action_discard_card)
                
                logger.info(f"Created discard card action for card_id={card.id}, position={card.position}")
        
        db.flush()
        
        # Robar cartas de reposición
        # Actor roba 1 carta (reposición por usar evento)
        actor_drawn = await robar_cartas_del_mazo(db, game, actor.id, 1)
        
        # Target roba tantas como NSF descartó
        target_drawn = []
        if len(target_nsf_cards) > 0:
            target_drawn = await robar_cartas_del_mazo(db, game, target.id, len(target_nsf_cards))
        
        db.commit()
        
        # Obtener mano restante del target
        target_remaining = db.query(CardsXGame).filter(
            CardsXGame.player_id == target.id,
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.HAND
        ).all()
        
        # Obtener info del discard pile
        top_discard = db.query(CardsXGame).filter(
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.DISCARD
        ).order_by(CardsXGame.position.desc()).first()
        
        discard_count = db.query(CardsXGame).filter(
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.DISCARD
        ).count()
        
        # Contar cartas en deck
        deck_remaining = db.query(CardsXGame).filter(
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.DECK
        ).count()
        
        # Construir respuesta
        response = CardsOffTableResponse(
            success=True,
            eventCardDiscarded=CardInfo(
                cardId=event_card.id,
                name=event_card.card.name if event_card.card else "Cards off the table",
                type=event_card.card.type.value if event_card.card and event_card.card.type else "EVENT"
            ),
            discardedNSFCards=discarded_nsf_info,
            sourcePlayerHand=PlayerHandInfo(
                player_id=actor.id,
                drawnCard=CardInfo(
                    cardId=actor_drawn[0].id,
                    name=actor_drawn[0].card.name if actor_drawn[0].card else "Unknown",
                    type=actor_drawn[0].card.type.value if actor_drawn[0].card and actor_drawn[0].card.type else "UNKNOWN",
                    position=actor_drawn[0].position
                ) if actor_drawn else None
            ),
            targetPlayerHand=PlayerHandInfo(
                player_id=target.id,
                discardedPositions=list(nsf_previous_positions.values()),
                drawnCards=[
                    CardInfo(
                        cardId=card.id,
                        name=card.card.name if card.card else "Unknown",
                        type=card.card.type.value if card.card and card.card.type else "UNKNOWN",
                        position=card.position
                    ) for card in target_drawn
                ],
                remainingCards=[
                    CardInfo(
                        cardId=card.id,
                        name=card.card.name if card.card else "Unknown",
                        type=card.card.type.value if card.card and card.card.type else "UNKNOWN",
                        position=card.position
                    ) for card in target_remaining
                ]
            ),
            discard=DiscardInfo(
                top=CardInfo(
                    cardId=top_discard.id,
                    name=top_discard.card.name if top_discard.card else "Unknown",
                    type=top_discard.card.type.value if top_discard.card and top_discard.card.type else "UNKNOWN"
                ),
                count=discard_count
            ),
            deck=DeckInfo(
                remaining=deck_remaining
            )
        )
        
        # Notificar por WebSocket
        game_state = build_complete_game_state(db, game.id)
        ws_service = get_websocket_service()
        
        await ws_service.notificar_estado_partida(
            room_id=room_id,
            jugador_que_actuo=actor.id,
            game_state=game_state
        )

        # Avanzar turno
        await actualizar_turno(db, game)
        
        logger.info(f"Cards off the table completed. NSF discarded: {len(discarded_nsf_info)}, Actor drew: {len(actor_drawn)}, Target drew: {len(target_drawn)}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in cards_off_the_table: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing cards off the table: {str(e)}"
        )
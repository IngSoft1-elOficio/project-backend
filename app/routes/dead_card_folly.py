# app/routes/dead_card_folly.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.services.dead_card_folly_service import DeadCardFollyService
from app.schemas.dead_card_folly_schema import (
    PlayDeadCardFollyRequest,
    PlayDeadCardFollyResponse,
    SelectCardRequest,
    SelectCardResponse
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/game", tags=["Games"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{room_id}/event/dead-card-folly/play", response_model=PlayDeadCardFollyResponse, status_code=200)
async def play_dead_card_folly(
    room_id: int,
    request: PlayDeadCardFollyRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint para jugar la carta Dead Card Folly y elegir dirección de intercambio.
    
    Flujo:
    1. Valida que es el turno del jugador
    2. Valida que la carta está en su mano y es Dead Card Folly
    3. Crea acción padre (EVENT_CARD) con dirección y estado PENDING
    4. Mueve la carta al descarte
    5. Notifica a todos los jugadores que deben seleccionar una carta
    6. Actualiza estados público y privado
    
    Args:
        room_id: ID de la sala
        request: Datos de la jugada (player_id, card_id, direction)
        actor_user_id: ID del jugador que juega la carta (header)
    
    Returns:
        PlayDeadCardFollyResponse con success=True y action_id
    
    Raises:
        400: Si la carta no está en la mano o no es Dead Card Folly
        403: Si no es el turno del jugador
        404: Si room/game/player/carta no existe
    """
    logger.info(f"POST /game/{room_id}/event/dead-card-folly/play received")
    logger.info(f"Request: player_id={request.player_id}, card_id={request.card_id}, direction={request.direction}")
    
    try:
        service = DeadCardFollyService(db)
        response = service.play_dead_card_folly(room_id, request)
        
        logger.info(
            f"✅ Dead Card Folly played successfully - "
            f"room_id={room_id}, player_id={request.player_id}, "
            f"direction={request.direction}, action_id={response.action_id}"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in play_dead_card_folly: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error playing Dead Card Folly: {str(e)}"
        )


@router.post("/{room_id}/event/dead-card-folly/select-card", response_model=SelectCardResponse, status_code=200)
async def select_card_for_exchange(
    room_id: int,
    request: SelectCardRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint para que cada jugador seleccione la carta que dará en el intercambio.
    
    Flujo:
    1. Valida que la acción padre existe y está PENDING
    2. Valida que la carta está en la mano del jugador
    3. Valida que el jugador no ha seleccionado ya
    4. Crea acción hija (CARD_EXCHANGE) con card_given_id y estado PENDING
    5. Si todos seleccionaron:
       - Ejecuta la rotación de cartas (swap de id_card)
       - Actualiza cada acción hija con card_received_id y estado SUCCESS
       - Actualiza acción padre a SUCCESS
       - Notifica finalización y actualiza estados
    6. Si faltan selecciones:
       - Retorna waiting=True con pending_count
    
    Args:
        room_id: ID de la sala
        request: Datos de la selección (action_id, card_id, player_id)
        actor_user_id: ID del jugador que selecciona (header)
    
    Returns:
        SelectCardResponse con:
        - success: True
        - waiting: True si faltan selecciones, False si completado
        - pending_count: Número de jugadores que faltan
        - message: Mensaje descriptivo
    
    Raises:
        400: Si acción no está PENDING, carta no está en mano, o ya seleccionó
        404: Si acción/carta/player no existe
    """
    logger.info(f"POST /game/{room_id}/event/dead-card-folly/select-card received")
    logger.info(f"Request: action_id={request.action_id}, card_id={request.card_id}, player_id={request.player_id}")
    
    try:
        service = DeadCardFollyService(db)
        response = service.select_card_for_exchange(room_id, request)
        
        if response.waiting:
            logger.info(
                f"✅ Card selected - Waiting for {response.pending_count} more players - "
                f"room_id={room_id}, player_id={request.player_id}, action_id={request.action_id}"
            )
        else:
            logger.info(
                f"✅ All cards selected - Rotation complete - "
                f"room_id={room_id}, action_id={request.action_id}"
            )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in select_card_for_exchange: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error selecting card for exchange: {str(e)}"
        )

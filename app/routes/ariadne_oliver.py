# app/routes/ariadne_oliver.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.services.ariadne_oliver_service import AriadneOliverService
from app.schemas.ariadne_oliver_schema import (
    AddOliverToSetRequest,
    AddOliverToSetResponse,
    OliverRevealSecretRequest,
    OliverRevealSecretResponse
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/game", tags=["Detective Actions"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post(
    "/{room_id}/detective/add-oliver-to-set",
    response_model=AddOliverToSetResponse,
    status_code=200
)
async def add_oliver_to_set(
    room_id: int,
    request: AddOliverToSetRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint para agregar Ariadne Oliver a un set existente de otro jugador.
    
    Flujo:
    1. Valida que es el turno del jugador
    2. Valida que la carta está en su mano y es Ariadne Oliver (id_card=5)
    3. Valida que el set objetivo existe
    4. Crea acción padre (ADD_DETECTIVE) con estado PENDING
    5. Mueve la carta al set objetivo (DETECTIVE_SET, hidden=False)
    6. Notifica al jugador objetivo que debe revelar un secreto
    7. Actualiza estados público y privado
    
    Args:
        room_id: ID de la sala
        request: Datos de la jugada (player_id, oliver_card_id, target_player_id, target_set_position)
    
    Returns:
        AddOliverToSetResponse con status, action_id, next_action y message
    
    Raises:
        400: Si la carta no está en la mano, no es Ariadne Oliver, o el set no existe
        403: Si no es el turno del jugador
        404: Si room/game/player/carta no existe
    """
    logger.info(f"POST /game/{room_id}/detective/add-oliver-to-set received")
    logger.info(
        f"Request: player_id={request.player_id}, oliver_card_id={request.oliver_card_id}, "
        f"target_player_id={request.target_player_id}, target_set_position={request.target_set_position}"
    )
    
    try:
        service = AriadneOliverService(db)
        response = service.add_oliver_to_set(room_id, request)
        
        logger.info(
            f"✅ Ariadne Oliver added successfully - "
            f"room_id={room_id}, player_id={request.player_id}, "
            f"target_player_id={request.target_player_id}, action_id={response.action_id}"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_oliver_to_set: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding Ariadne Oliver to set: {str(e)}"
        )


@router.post(
    "/{room_id}/detective/oliver-reveal-secret",
    response_model=OliverRevealSecretResponse,
    status_code=200
)
async def oliver_reveal_secret(
    room_id: int,
    request: OliverRevealSecretRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint para que el jugador objetivo revele un secreto propio por efecto de Ariadne Oliver.
    
    Flujo:
    1. Valida que la acción padre existe y está PENDING
    2. Valida que el secreto pertenece al jugador objetivo
    3. Actualiza CardsXGame.hidden = FALSE
    4. Crea acción hija (REVEAL_SECRET) con action_name=ARIADNE_OLIVER_EFFECT
    5. Actualiza acción padre a SUCCESS
    6. Verifica social disgrace
    7. Verifica si se reveló el asesino (fin de juego)
    8. Notifica finalización y actualiza estados
    
    Args:
        room_id: ID de la sala
        request: Datos de la revelación (action_id, secret_id, player_id)
    
    Returns:
        OliverRevealSecretResponse con status y message
    
    Raises:
        400: Si acción no está PENDING o secreto no está en SECRET_SET
        403: Si el jugador no es el target de la acción
        404: Si acción/secreto no existe
    """
    logger.info(f"POST /game/{room_id}/detective/oliver-reveal-secret received")
    logger.info(
        f"Request: action_id={request.action_id}, secret_id={request.secret_id}, "
        f"player_id={request.player_id}"
    )
    
    try:
        service = AriadneOliverService(db)
        response = service.oliver_reveal_secret(room_id, request)
        
        logger.info(
            f"✅ Ariadne Oliver effect complete - "
            f"room_id={room_id}, player_id={request.player_id}, "
            f"secret_id={request.secret_id}"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in oliver_reveal_secret: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error revealing secret for Ariadne Oliver: {str(e)}"
        )

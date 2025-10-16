from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Room
from app.schemas.detective_set_schema import (
    PlayDetectiveSetRequest, 
    PlayDetectiveSetResponse
)
from app.services.detective_set_service import DetectiveSetService
from app.services.game_status_service import build_complete_game_state
from app.sockets.socket_service import get_websocket_service

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/game", tags=["Games"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post(
    "/{room_id}/play-detective-set", 
    response_model=PlayDetectiveSetResponse, 
    status_code=200
)
async def play_detective_set(
    room_id: int,
    request: PlayDetectiveSetRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint para bajar un set de detectives.
    
    Valida el set, actualiza CardsXGame, crea la acción PENDING en ActionsPerTurn,
    y emite eventos WebSocket notificando el inicio de la acción.
    """
    logger.info(f"🎯 POST /api/game/{room_id}/play-detective-set - Player {request.owner}")
    
    # 1. Validar que la room existe
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if not room.id_game:
        raise HTTPException(status_code=409, detail="Game not started")
    
    game_id = room.id_game
    
    # 2. Ejecutar la lógica de negocio en el servicio
    try:
        service = DetectiveSetService(db)
        action_id, next_action = service.play_detective_set(game_id, request)
        
        logger.info(f"Detective set played successfully. Action ID: {action_id}")
        
    except HTTPException:
        # Re-lanzar excepciones HTTP del servicio
        raise
    except Exception as e:
        logger.error(f"Error playing detective set: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    # 3. Obtener estado completo del juego para WebSocket
    try:
        game_state = build_complete_game_state(db, game_id)
    except Exception as e:
        logger.error(f"Error building game state: {str(e)}")
        game_state = {}
    
    # 4. Emitir eventos WebSocket
    ws_service = get_websocket_service()
    
    try:
        # Notificar que la acción de detective comenzó
        await ws_service.notificar_detective_action_started(
            room_id=room_id,
            player_id=request.owner,
            set_type=request.setType.value
        )
        logger.info(f"📡 Emitted detective_action_started to room {room_id}")
        
        # Notificar estado completo del juego (público y privado)
        await ws_service.notificar_estado_partida(
            room_id=room_id,
            jugador_que_actuo=request.owner,
            game_state=game_state
        )
        logger.info(f"📡 Emitted game state to room {room_id}")
        
    except Exception as e:
        logger.error(f"Error emitting WebSocket events: {str(e)}")
        # No fallar el request si solo falló el WS
    
    # 5. Construir y retornar response
    response = PlayDetectiveSetResponse(
        success=True,
        actionId=action_id,
        nextAction=next_action
    )
    
    logger.info(f"Response: {response.model_dump()}")
    
    return response

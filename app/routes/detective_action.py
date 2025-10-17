# app/routes/detective_action.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Room
from app.schemas.detective_action_schema import (
    DetectiveActionRequest,
    DetectiveActionResponse
)
from app.services.detective_action_service import DetectiveActionService
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
    "/{room_id}/detective-action",
    response_model=DetectiveActionResponse,
    status_code=200
)
async def execute_detective_action(
    room_id: int,
    request: DetectiveActionRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint para ejecutar una acción de detective pendiente.
    
    Ejecuta el efecto correspondiente según el tipo de detective:
    - Poirot/Marple: Revelan un secreto elegido por el activo
    - Parker Pyne: Oculta un secreto revelado elegido por el activo
    - Beresford/Eileen/Satterthwaite: El target revela su propio secreto
    - Satterthwaite con wildcard: Además transfiere el secreto revelado al activo
    
    Actualiza CardsXGame, marca la acción como SUCCESS, y emite eventos WebSocket.
    """
    logger.info(
        f"POST /api/game/{room_id}/detective-action - "
        f"Executor {request.executorId}, Action {request.actionId}"
    )
    
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if not room.id_game:
        raise HTTPException(status_code=409, detail="Game not started")
    
    game_id = room.id_game
    
    try:
        service = DetectiveActionService(db)
        response = service.execute_detective_action(game_id, request)
        
        logger.info(f"Detective action executed successfully. Effects: {response.effects}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing detective action: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    try:
        game_state = build_complete_game_state(db, game_id)
    except Exception as e:
        logger.error(f"Error building game state: {str(e)}")
        game_state = {}
    
    ws_service = get_websocket_service()
    
    try:
        action_type = "unknown"
        action = "revealed"
        secret_id = None
        target_player_id = request.targetPlayerId if request.targetPlayerId else request.executorId
        wildcard_used = False
        
        if response.effects.revealed:
            action = "revealed"
            secret_id = response.effects.revealed[0].secretId
            target_player_id = response.effects.revealed[0].playerId
        elif response.effects.hidden:
            action = "hidden"
            secret_id = response.effects.hidden[0].secretId
            target_player_id = response.effects.hidden[0].playerId
        elif response.effects.transferred:
            action = "transferred"
            secret_id = response.effects.transferred[0].secretId
            target_player_id = response.effects.transferred[0].fromPlayerId
            wildcard_used = True
        
        await ws_service.notificar_detective_action_complete(
            room_id=room_id,
            action_type=action_type,
            player_id=request.executorId,
            target_player_id=target_player_id,
            secret_id=secret_id,
            action=action,
            wildcard_used=wildcard_used
        )
        logger.info(f"Emitted detective_action_complete to room {room_id}")
        
        await ws_service.notificar_estado_partida(
            room_id=room_id,
            jugador_que_actuo=request.executorId,
            game_state=game_state
        )
        logger.info(f"Emitted game state to room {room_id}")
        
    except Exception as e:
        logger.error(f"Error emitting WebSocket events: {str(e)}")
    
    logger.info(f"Response: {response.model_dump()}")
    
    return response

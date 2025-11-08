from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Room
from app.schemas.not_so_fast_schema import (
    StartActionRequest,
    StartActionResponse
)
from app.services.not_so_fast_service import NotSoFastService
from app.services.game_status_service import build_complete_game_state
from app.services.timer_manager import get_timer_manager
from app.services.counter_timeout_handler import handle_nsf_timeout
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
    "/{room_id}/start-action",
    response_model=StartActionResponse,
    status_code=200
)
async def start_action(
    room_id: int,
    request: StartActionRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint para iniciar una acción que puede ser contrarrestada con Not So Fast.
    
    Valida la acción, determina si es cancelable, chequea si hay jugadores con NSF,
    y crea los registros correspondientes en ActionsPerTurn.
    
    Si la acción es cancelable y hay jugadores con NSF:
    - Crea una acción de intención (INTENTION)
    - Crea una acción NSF de inicio (INSTANT_START)
    - Emite eventos WebSocket para iniciar la ventana NSF
    - Retorna cancellable=true y timeRemaining=5
    
    Si la acción NO es cancelable o NO hay jugadores con NSF:
    - Crea solo la acción de intención (INTENTION) con result=CONTINUE
    - Retorna cancellable=false
    """
    logger.info(f"POST /api/game/{room_id}/start-action - Player {request.playerId}")
    
    # 1. Validar que la room existe
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if not room.id_game:
        raise HTTPException(status_code=400, detail="Room has no active game")
    
    game_id = room.id_game
    
    try:
        # 2. Ejecutar la lógica de negocio
        service = NotSoFastService(db)
        response = service.start_action(room_id, request)
        
        ws_service = get_websocket_service()
        
        # 3. Emitir eventos WebSocket según el caso
        # Determinar el nombre de la acción para los eventos
        action_type_display = request.additionalData.actionType if request.additionalData else "EVENT_CARD"
        
        # Emitir VALID_ACTION siempre (la acción es válida)
        await ws_service.notificar_valid_action(
            room_id=room_id,
            action_id=response.actionId,
            player_id=request.playerId,
            action_type=action_type_display,
            action_name=f"Card(s): {request.cardIds}",
            cancellable=response.cancellable
        )
        
        # Si la acción es cancelable y se creó una ventana NSF
        if response.cancellable and response.actionNSFId is not None:
            # Emitir NSF_COUNTER_START
            await ws_service.notificar_nsf_counter_start(
                room_id=room_id,
                action_id=response.actionId,
                nsf_action_id=response.actionNSFId,
                player_id=request.playerId,
                action_type=action_type_display,
                action_name=f"Card(s): {request.cardIds}",
                time_remaining=response.timeRemaining or 0
            )
            
            # Iniciar timer para NSF_COUNTER_TICK
            timer_manager = get_timer_manager()
            
            async def on_tick(room_id: int, nsf_action_id: int, time_remaining: int):
                """Callback para cada tick del timer."""
                # Calcular tiempo transcurrido
                total_time = response.timeRemaining or 5
                elapsed_time = total_time - time_remaining
                
                await ws_service.notificar_nsf_counter_tick(
                    room_id=room_id,
                    action_id=nsf_action_id,
                    remaining_time=time_remaining,
                    elapsed_time=elapsed_time
                )
            
            async def on_complete(room_id: int, nsf_action_id: int, was_cancelled: bool):
                """Callback cuando el timer termina."""
                if not was_cancelled:
                    # Timer terminó naturalmente (llegó a 0)
                    # Calcular resultado según cantidad de NSF jugadas
                    logger.info(
                        f"⏰ Timer NSF terminó para action {nsf_action_id} - "
                        f"Calculando resultado según NSF jugadas..."
                    )
                    
                    # Llamar al handler que cuenta NSF y determina el resultado
                    await handle_nsf_timeout(
                        db=db,
                        room_id=room_id,
                        intention_action_id=response.actionId,  # XXX
                        nsf_action_id=nsf_action_id             # YYY
                    )
            
            await timer_manager.start_timer(
                room_id=room_id,
                nsf_action_id=response.actionNSFId,
                time_remaining=response.timeRemaining or 5,
                on_tick_callback=on_tick,
                on_complete_callback=on_complete
            )
        
        # 4. Emitir actualización de estado del juego
        game_state = build_complete_game_state(db, game_id)
        
        await ws_service.notificar_estado_partida(
            room_id=room_id,
            jugador_que_actuo=request.playerId,
            game_state=game_state
        )
        
        logger.info(
            f" Action started - "
            f"actionId={response.actionId}, "
            f"cancellable={response.cancellable}, "
            f"nsfActionId={response.actionNSFId}"
        )
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in start_action: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

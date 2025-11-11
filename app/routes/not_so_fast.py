from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Room
from app.db import crud
from app.schemas.not_so_fast_schema import (
    StartActionRequest,
    StartActionResponse,
    PlayNSFRequest,
    PlayNSFResponse,
    CancelNSFRequest,
    CancelNSFResponse
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


@router.post(
    "/{room_id}/instant/not-so-fast",
    response_model=PlayNSFResponse,
    status_code=200
)
async def play_not_so_fast(
    room_id: int,
    request: PlayNSFRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint para jugar una carta Not So Fast.
    
    Valida que la carta NSF esté en la mano del jugador, crea una nueva acción,
    actualiza la acción NSF_START con el nuevo tiempo, mueve la carta al descarte,
    reinicia el timer y emite eventos WebSocket.
    
    Args:
        room_id: ID de la sala
        request: PlayNSFRequest con actionId (XXX), playerId, cardId
    
    Returns:
        PlayNSFResponse con nsfActionId (ZZZ), nsfStartActionId (YYY), timeRemaining
    """
    logger.info(
        f"POST /api/game/{room_id}/instant/not-so-fast - "
        f"Player {request.playerId} plays NSF on action {request.actionId}"
    )
    
    # 1. Validar que la room existe
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if not room.id_game:
        raise HTTPException(status_code=400, detail="Room has no active game")
    
    game_id = room.id_game
    
    try:
        # 2. Ejecutar lógica de negocio (crear acción ZZZ, actualizar YYY)
        service = NotSoFastService(db)
        nsf_action_id, nsf_start_action_id, player_name = service.play_nsf_card(
            room_id=room_id,
            action_id=request.actionId,
            player_id=request.playerId,
            card_id=request.cardId
        )
        
        # 3. Mover la carta NSF al descarte
        crud.move_card_to_discard(db, request.cardId, game_id)
        
        # 4. Obtener el estado actualizado del juego
        ws_service = get_websocket_service()
        game_state = build_complete_game_state(db, game_id)
        
        # 5. Emitir eventos WebSocket
        
        # 5a. Actualización de estado público (descarte actualizado)
        await ws_service.notificar_estado_partida(
            room_id=room_id,
            jugador_que_actuo=request.playerId,
            game_state=game_state
        )
        
        # 5b. Evento NSF_PLAYED
        await ws_service.notificar_nsf_played(
            room_id=room_id,
            action_id=nsf_start_action_id,  # YYY
            nsf_action_id=nsf_action_id,    # ZZZ
            player_id=request.playerId,
            card_id=request.cardId,
            player_name=player_name,
        )
        
        # 6. Reiniciar el timer (cancelar el viejo y crear uno nuevo con 5s)
        timer_manager = get_timer_manager()
        
        async def on_tick(room_id: int, nsf_action_id: int, time_remaining: int):
            """Callback para cada tick del timer."""
            total_time = 10
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
                logger.info(
                    f"⏰ Timer NSF terminó para action {nsf_action_id} - "
                    f"Calculando resultado según NSF jugadas..."
                )
                
                # Llamar al handler que cuenta NSF y determina el resultado
                await handle_nsf_timeout(
                    db=db,
                    room_id=room_id,
                    intention_action_id=request.actionId,  # XXX
                    nsf_action_id=nsf_action_id            # YYY
                )
        
        # Reiniciar timer (esto cancela el viejo y crea uno nuevo)
        await timer_manager.start_timer(
            room_id=room_id,
            nsf_action_id=nsf_start_action_id,  # YYY (mismo ID, se reinicia)
            time_remaining=10,
            on_tick_callback=on_tick,
            on_complete_callback=on_complete
        )
        
        logger.info(
            f"✅ NSF played successfully - "
            f"nsfActionId={nsf_action_id}, "
            f"nsfStartActionId={nsf_start_action_id}, "
            f"timer restarted"
        )
        
        message = f"Player {player_name} jugó Not So Fast"
        
        return PlayNSFResponse(
            success=True,
            nsfActionId=nsf_action_id,
            nsfStartActionId=nsf_start_action_id,
            timeRemaining=5,
            message=message
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in play_not_so_fast: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post(
    "/{room_id}/instant/not-so-fast/cancel",
    response_model=CancelNSFResponse,
    status_code=200
)
async def cancel_nsf_action(
    room_id: int,
    request: CancelNSFRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint para ejecutar una acción que fue cancelada por Not So Fast.
    
    Simula que la acción fue 'jugada' pero sin ejecutar su efecto real.
    Las cartas involucradas se mueven según las reglas especiales:
    
    - CREATE_SET: Si contiene Eileen Brent, las cartas quedan en HAND.
                  Si no, se crea el set sin ejecutar efecto y las cartas van al set.
    - EVENT: La carta se inserta en el descarte en la posición nsf_count+1 
             (debajo de todas las NSF jugadas).
    - ADD_TO_SET: 
        * Ariadne Oliver: Se agrega al set del jugador target (otro jugador).
        * Eileen Brent: Queda en HAND del jugador que la jugó.
        * Otras: Se agregan al set del jugador que las jugó.
    
    Args:
        room_id: ID de la sala
        request: CancelNSFRequest con:
            - actionId: ID de la acción de intención (XXX) que fue cancelada
            - playerId: ID del jugador que ejecuta la acción cancelada
            - cardIds: IDs de las cartas involucradas
            - additionalData: Datos adicionales según tipo de acción (actionType, etc.)
    
    Returns:
        CancelNSFResponse con success y message descriptivo
    """
    logger.info(
        f"POST /api/game/{room_id}/instant/not-so-fast/cancel - "
        f"Player {request.playerId} executes cancelled action {request.actionId}"
    )
    
    # 1. Validar que la room existe
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if not room.id_game:
        raise HTTPException(status_code=400, detail="Room has no active game")
    
    game_id = room.id_game
    
    try:
        # 2. Ejecutar lógica de negocio (procesar acción cancelada)
        service = NotSoFastService(db)
        message = service.cancel_nsf_action(
            room_id=room_id,
            action_id=request.actionId,
            player_id=request.playerId,
            card_ids=request.cardIds,
            additional_data=request.additionalData
        )
        
        # 3. Confirmar los cambios en la base de datos
        db.commit()
        
        # 4. Obtener el estado actualizado del juego
        ws_service = get_websocket_service()
        game_state = build_complete_game_state(db, game_id)
        
        # 5. Emitir eventos WebSocket
        
        # 5a. Actualización de estado público (cartas movidas, sets actualizados, etc.)
        await ws_service.notificar_estado_partida(
            room_id=room_id,
            jugador_que_actuo=request.playerId,
            game_state=game_state
        )
        
        # 5b. Evento CANCELLED_ACTION_EXECUTED
        await ws_service.notificar_accion_cancelada_ejecutada(
            room_id=room_id,
            action_id=request.actionId,
            player_id=request.playerId,
            message=message
        )
        
        logger.info(
            f"✅ Cancelled action executed successfully - "
            f"actionId={request.actionId}, "
            f"playerId={request.playerId}"
        )
        
        return CancelNSFResponse(
            success=True,
            message=message
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in cancel_nsf_action: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

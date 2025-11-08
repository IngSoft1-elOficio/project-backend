"""
Handler para la finalización del contador de Not So Fast.

Cuando el timer llega a 0, este servicio:
1. Cuenta cuántas NSF se jugaron (parent_action_id = YYY)
2. Calcula el resultado: CANCELLED si impar, CONTINUE si par
3. Actualiza los registros en DB
4. Emite NSF_COUNTER_COMPLETE
"""

import logging
from sqlalchemy.orm import Session
from app.db import crud
from app.db.models import ActionResult, ActionType
from app.sockets.socket_service import get_websocket_service

logger = logging.getLogger(__name__)


async def handle_nsf_timeout(
    db: Session,
    room_id: int,
    intention_action_id: int,  # XXX - la acción original de intención
    nsf_action_id: int         # YYY - la acción NSF start
):
    """
    Maneja el timeout del contador NSF.
    
    Cuenta las NSF jugadas, determina si la acción se cancela o continúa,
    actualiza los registros y emite el evento final.
    
    Args:
        db: Sesión de base de datos
        room_id: ID de la sala
        intention_action_id: ID de la acción de intención original (XXX)
        nsf_action_id: ID de la acción NSF start (YYY)
    """
    logger.info(
        f"⏰ Procesando timeout NSF - "
        f"intention_action={intention_action_id}, nsf_action={nsf_action_id}"
    )
    
    try:
        # 1. Contar cuántas NSF se jugaron en esta cadena
        # Buscar todas las acciones con:
        #   - parent_action_id = YYY (la cadena NSF)
        #   - triggered_by_action_id = XXX (la acción original)
        #   - action_name = "NOT_SO_FAST"
        nsf_chain = crud.get_actions_by_filters(
            db,
            parent_action_id=nsf_action_id,
            triggered_by_action_id=intention_action_id
        )
        
        nsf_chain_len = len(nsf_chain)
        
        logger.info(f"📊 NSF jugadas en la cadena: {nsf_chain_len}")
        
        # 2. Calcular resultado según paridad
        if nsf_chain_len % 2 != 0:
            # Impar → la acción se CANCELA
            final_result = ActionResult.CANCELLED      # YYY
            intention_result = ActionResult.CANCELLED  # XXX
            result_str = "cancelled"
            logger.info("❌ Acción CANCELADA (NSF impar)")
        else:
            # Par (incluyendo 0) → la acción CONTINÚA
            final_result = ActionResult.SUCCESS     # YYY
            intention_result = ActionResult.CONTINUE  # XXX
            result_str = "continue"
            logger.info("✅ Acción CONTINÚA (NSF par)")
        
        # 3. Actualizar registros en DB
        # Actualizar YYY (acción NSF start) → SUCCESS o CANCELLED
        crud.update_action_result(db, nsf_action_id, final_result)
        
        # Actualizar XXX (acción de intención) → CONTINUE o CANCELLED
        crud.update_action_result(db, intention_action_id, intention_result)
        
        # Actualizar todas las acciones ZZZ (INSTANT_PLAY) → Siempre SUCCESS
        # (las NSF se jugaron correctamente, independientemente del resultado)
        for nsf_play_action in nsf_chain:
            crud.update_action_result(db, nsf_play_action.id, ActionResult.SUCCESS)
        
        logger.info(f"✅ Actualizadas {nsf_chain_len} acciones NSF_PLAY a SUCCESS")
        
        db.commit()
        
        logger.info(
            f"✅ Registros actualizados - "
            f"YYY({nsf_action_id})={final_result}, "
            f"XXX({intention_action_id})={intention_result}, "
            f"{nsf_chain_len} ZZZ actions=SUCCESS"
        )
        
        # 4. Emitir evento NSF_COUNTER_COMPLETE
        ws_service = get_websocket_service()
        
        # Construir mensaje descriptivo
        if nsf_chain_len == 0:
            message = "NSF counter finished - No NSF played, action continues"
        elif nsf_chain_len == 1:
            message = "NSF counter finished - 1 NSF played, action cancelled"
        else:
            action_status = "cancelled" if result_str == "cancelled" else "continues"
            message = f"NSF counter finished - {nsf_chain_len} NSF played, action {action_status}"
        
        await ws_service.notificar_nsf_counter_complete(
            room_id=room_id,
            action_id=intention_action_id,
            final_result=result_str,
            message=message
        )
        
        logger.info(
            f"📡 Evento NSF_COUNTER_COMPLETE emitido - "
            f"result={result_str}, message={message}"
        )
        
    except Exception as e:
        logger.error(f"❌ Error en handle_nsf_timeout: {e}")
        db.rollback()
        raise

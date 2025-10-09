# app/sockets/socket_service.py
from .socket_manager import get_ws_manager
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketService:
    """Interface publica para que otros servicios usen WebSocket"""
    def __init__(self):
        self.ws_manager = get_ws_manager()
    
    async def notificar_estado_partida(
        self,
        room_id: int,
        jugador_que_actuo: Optional[int] = None,
        game_state: Optional[Dict] = None,
        partida_finalizada: bool = False,
    ):
        logger.info(f"🎮 Notifying room {room_id}")
        sids = self.ws_manager.get_sids_in_game(room_id)
        logger.info(f"Found {len(sids)} connected players in room {room_id}: {sids}")

        if not sids:
            logger.warning(f"Room {room_id} vacia")
            return
        
        mensaje_publico = {
            "type": "game_state_public",
            "room_id": room_id,
            "game_id": game_state.get("game_id") if game_state else None,
            "status": game_state.get("status") if game_state else "WAITING",
            "turno_actual": game_state.get("turno_actual") if game_state else jugador_que_actuo,
            "jugadores": game_state.get("jugadores", []),
            "mazos": game_state.get("mazos", {}),
            "game_ended": partida_finalizada,  
            "winners": game_state.get("winners", []) if partida_finalizada else [],  
            "finish_reason": game_state.get("finish_reason") if partida_finalizada else None,  
            "timestamp": datetime.now().isoformat()
        }                                                   
        
        await self.ws_manager.emit_to_room(room_id, "game_state_public", mensaje_publico)
        logger.info(f"✅ Emitted game_state_public to room {room_id}")
        
        for sid in sids:
            session = self.ws_manager.get_user_session(sid)
            if not session:
                continue
            
            user_id = session["user_id"]
            
            mensaje_privado = {
                "type": "game_state_private",
                "user_id": user_id,
                "mano": game_state.get("manos", {}).get(user_id, []) if game_state else [],
                "secretos": game_state.get("secretos", {}).get(user_id, []) if game_state else [],
                "timestamp": datetime.now().isoformat()
            }
            await self.ws_manager.emit_to_sid(sid, "game_state_private", mensaje_privado)
            logger.info(f"Emitted game_state_private to user {user_id} in room {room_id}")
            
            if jugador_que_actuo and user_id == jugador_que_actuo:
                feedback = {
                    "type": "player_action_result",
                    "success": True,
                    "mensaje": "Accion valida",
                    "timestamp": datetime.now().isoformat()
                }
                await self.ws_manager.emit_to_sid(sid, "player_action_result", feedback)
            
            if partida_finalizada:
                # Check if this user is a winner
                is_winner = any(w.get("player_id") == user_id for w in game_state.get("winners", []))
                
                resultado = {
                    "type": "game_ended",
                    "user_id": user_id,
                    "ganaste": is_winner,
                    "winners": game_state.get("winners", []),
                    "reason": game_state.get("finish_reason"),
                    "timestamp": datetime.now().isoformat()
                }
                await self.ws_manager.emit_to_sid(sid, "game_ended", resultado)

_websocket_service = None

def get_websocket_service() -> WebSocketService:
    global _websocket_service
    if _websocket_service is None:
        _websocket_service = WebSocketService()
    return _websocket_service
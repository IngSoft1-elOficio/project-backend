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
    
    # Aca impementar los servicios del socket 

    async def notificar_estado_partida(
            self, game_id: int, 
            jugador_que_actuo: Optional[int] = None, 
            game_state: Optional[Dict[str, Any]] = None, 
            partida_finalizada: bool = False,
            ganador_id: Optional[int] = None
    ):
        """Envia notificaciones publicas y privadas del estado del juego"""

        print("🎮 Notifying game {game_id}")

        # Obtengo manager y los sids activos
        sids = self.ws_manager.get_sids_in_game(game_id)

        logger.info(f"🎮 Notifying game {game_id}, found {len(sids)} connected players: {sids}")

        if not sids:
            logger.warning(f"room {game_id} vacia")
            return
        
        mensaje_publico = {
            "type": "game_state_public",
            "game_id": game_id,
            "status": game_state.get("status"),
            "turno_actual": game_state.get("turno_actual") if game_state else jugador_que_actuo,
            "jugadores": game_state.get("jugadores") if game_state else [],
            "mazos": game_state.get("mazos") if game_state else {},
            "timestamp": datetime.now().isoformat()
        }

        # Emito el mensaje publico a los jugadores en el room
        await self.ws_manager.emit_to_room(game_id, "game_state_public", mensaje_publico)
        logger.info(f"✅ Emitted game_state_public to room {game_id}")

        # Mensajes privados
        for sid in sids:
            session = self.ws_manager.get_user_session(sid)
            if not session:
                continue
            
            user_id = session["user_id"]

            # Estado privado para cada jugador
            mensaje_privado = {
                "type": "game_state_private",
                "user_id": user_id,
                "mano": game_state.get("manos", {}).get(user_id, []) if game_state else [],
                "secretos": game_state.get("secretos", {}).get(user_id, []) if game_state else [],
                "timestamp": datetime.now().isoformat()
            }

            await self.ws_manager.emit_to_sid(sid, "game_state_private", mensaje_privado)

            # Feedback de la accion
            if jugador_que_actuo and user_id == jugador_que_actuo:
                feedback = {
                    "type": "player_action_result",
                    "success": True,
                    "mensaje": "Accion valida",
                    "timestamp": datetime.now().isoformat()
                }

                await self.ws_manager.emit_to_sid(sid, "player_action_result", feedback)
            
            # Partida finalizada
            if partida_finalizada:
                resultado = {
                    "type": "game_ended",
                    "user_id": user_id,
                    "ganaste": True if ganador_id and user_id == ganador_id else False,
                    "timestamp": datetime.now().isoformat()
                }

                await self.ws_manager.emit_to_sid(sid, "game_ended", resultado)


_websocket_service = None

def get_websocket_service() -> WebSocketService:
    global _websocket_service
    if _websocket_service is None:
        _websocket_service = WebSocketService()
    return _websocket_service

import socketio 
from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketManager:
    # Constructor
    def __init__(self, sio: socketio.AsyncServer):
        self.sio = sio
        # tracking interno: sid -> {user_id, game_id, connected_at}
        # self.user_sessions: Dict[str, dict] = {}

    def get_room_name(self, game_id: int) -> str:
        """Genera nombre estandar del room para una partida"""
        return f"game_{game_id}"

    async def join_game_room(self, sid: str, game_id: int, user_id: int) -> bool:
        """Une a un jugador al room de su partida"""
        try: 
            room = self.get_room_name(game_id)

            # Implentar: Validar que el usuario puede acceder a esta partida
            await self.sio.enter_room(sid, room)

            # actualizar tracking interno

            # notificar a otros jugadores en el room
            await self.sio.emit('player_connected', {
                'user_id': user_id,
                'game_id': game_id,
                'timestamp': datetime.now().isoformat()
            }, room=room, skip_sid=sid)

            logger.info(f"Usuario {user_id} se unió a room {room}")
            return True
        except Exception as e:
            logger.error(f"Error joining room: {e}")
            await self.sio.emit('error', {'message': 'Error unindose a la partida'}, room=sid)
            return False

# Instancia global
_ws_manager: Optional[WebSocketManager] = None

def get_ws_manager() -> WebSocketManager:
    global _ws_manager
    if _ws_manager is None:
        raise RuntimeError("WebSocketManager no inicializado")
    return _ws_manager

def init_ws_manager(sio: socketio.AsyncServer) -> WebSocketManager:
    global _ws_manager
    _ws_manager = WebSocketManager(sio)
    return _ws_manager

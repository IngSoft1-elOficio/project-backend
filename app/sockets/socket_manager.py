import socketio 
from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketManager:

    def __init__(self, sio: socketio.AsyncServer):
        self.sio = sio
        # tracking interno: sid -> {user_id, game_id, connected_at} se pierde si se cae el server
        self.user_sessions: Dict[str, dict] = {}

    def get_room_name(self, game_id: int) -> str:
        """Genera nombre estandar del room para una partida"""
        return f"game_{game_id}"

    async def join_game_room(self, sid: str, game_id: int, user_id: int) -> bool:
        """Une a un jugador al room de su partida"""
        try:
            room = self.get_room_name(game_id)
            
            # Implementar: Validar que el usuario puede acceder a esta partida
            await self.sio.enter_room(sid, room)
            
            # actualizar tracking interno
            self.user_sessions[sid] = {
                'user_id': user_id,
                'game_id': game_id,
                'connected_at': datetime.now().isoformat()
            }
            
            # notificar a otros jugadores en el room (skip current user)
            await self.sio.emit('player_connected', {
                'user_id': user_id,
                'game_id': game_id,
                'timestamp': datetime.now().isoformat()
            }, room=room, skip_sid=sid)

            await self.sio.emit('game_state_public', {
                'game_id': game_id,
                'status': 'WAITING',
                'turno_actual': None,
                'jugadores': await self.get_room_participants(game_id),
                'mazos': {},
                'timestamp': datetime.now().isoformat()
            }, room=room)
            
            logger.info(f"Usuario {user_id} se unió a room {room}")
            return True
            
        except Exception as e:
            logger.error(f"Error joining room: {e}")
            await self.sio.emit('error', {'message': 'Error uniendose a la partida'}, room=sid)
            return False

    async def leave_game_room(self, sid: str):
        """Salir del room"""
        try: 
            if sid not in self.user_sessions:
                return
            
            session_data = self.user_sessions[sid]
            game_id = session_data['game_id']
            user_id = session_data['user_id']
            room = self.get_room_name(game_id)

            # salir de la room
            await self.sio.leave_room(sid, room)

            # notificar a otros jugadores
            await self.sio.emit('leaved_room', {
                'user_id': user_id,
                'game_id': game_id,
                'timestamp': datetime.now().isoformat()
            }, room=room)

            # limpiar tracking
            del self.user_sessions[sid]

            logger.info(f"Usuario {user_id} salio de room {room}")
        
        except Exception as e:
            logger.error(f"Error leaving room: {e}")

    async def get_room_participants(self, game_id: int) -> List[dict]:
        """Obtiene la lista de participantes en el room"""
        room = self.get_room_name(game_id)
        participants = []

        for sid, session_data in self.user_sessions.items():
            if session_data.get('game_id') == game_id:
                participants.append({
                    'sid': sid,
                    'user_id': session_data['user_id'],
                    'connected_at': session_data['connected_at']
                })

        return participants

    # Metodos para las notificaciones

    async def emit_to_room(self, game_id: int, event: str, data: Dict):
        """Emite un evento a todos los jugadores en una partida"""
        room = self.get_room_name(game_id) # Tomo a que partida le mando la notificacion
        # Chequeo que la room no este vacia
        if not any(s['game_id'] == game_id for s in self.user_sessions.values()):
          logger.warning(f"La room esta vacía: {room}")
          return
        
        await self.sio.emit(event, data, room=room)
    
    async def emit_to_sid(self, sid: str, event: str, data: Dict):
        """Emite un evento privado a un jugador"""
        await self.sio.emit(event, data, to=sid)
    
    def get_sids_in_game(self, game_id: int) -> List[str]:
        """Devuelve los SIDs de los jugadores conectados en la room"""
        return [
            sid for sid, s in self.user_sessions.items()
            if s['game_id'] == game_id
        ]
    
    def get_user_session(self, sid: str) -> Optional[dict]:
        """Devuelve la sesión del usuario si esta conectado"""
        return self.user_sessions.get(sid)

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

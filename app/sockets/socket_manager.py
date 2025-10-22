import socketio 
from typing import Dict, List, Optional
import logging
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class WebSocketManager:

    def __init__(self, sio: socketio.AsyncServer, db_factory):
        self.sio = sio
        # tracking interno: sid -> {user_id, game_id, connected_at} se pierde si se cae el server
        self.db_factory = db_factory  # Función que retorna una Session de DB
        self.user_sessions: Dict[str, dict] = {}

    def get_room_name(self, room_id: int) -> str:
        """Genera nombre estandar del room para una partida"""
        return f"game_{room_id}"

    async def join_game_room(self, sid: str, room_id: int, user_id: int) -> bool:
        """Une a un jugador al room de su partida"""
        try:
            room = self.get_room_name(room_id)
            
            # Implementar: Validar que el usuario puede acceder a esta partida
            await self.sio.enter_room(sid, room)
            
            # actualizar tracking interno
            self.user_sessions[sid] = {
                'user_id': user_id,
                'room_id': room_id,
                'connected_at': datetime.now().isoformat()
            }
            logger.debug(f"User {user_id} joined room {room} with sid {sid}, sessions: {self.user_sessions}")
            
            # notificar a otros jugadores en el room (skip current user)
            await self.sio.emit('player_connected', {
                'user_id': user_id,
                'room_id': room_id,
                'timestamp': datetime.now().isoformat()
            }, room=room, skip_sid=sid)

            # Obtener participantes con datos completos de la DB
            participants = await self.get_room_participants(room_id)

            await self.sio.emit('game_state_public', {
                'room_id': room_id,
                'status': 'WAITING',
                'turno_actual': None,
                'jugadores': participants,
                'mazos': {},
                'timestamp': datetime.now().isoformat()
            }, room=room)
            
            logger.info(f"Usuario {user_id} se unió a room {room}")
            return True
            
        except Exception as e:
            logger.error(f"Error joining room: {e}")
            await self.sio.emit('error', {'message': 'Error uniendose a la partida'}, room=sid)
            return False

    async def leave_game_room(self, sid: str, room_id: int = None):
        """Salir del room"""
        try: 
            if sid not in self.user_sessions:
                return
            
            session_data = self.user_sessions[sid]
            # Si room_id no se proporciona, usar room_id de la sesión
            if room_id is None:
                room_id = session_data.get('room_id')
            user_id = session_data['user_id']
            room = self.get_room_name(room_id)

            # salir de la room
            await self.sio.leave_room(sid, room)

            # notificar a otros jugadores
            await self.sio.emit('player_disconnected', {
                'user_id': user_id,
                'room_id': room_id,
                'timestamp': datetime.now().isoformat()
            }, room=room)

            # limpiar tracking
            del self.user_sessions[sid]

            logger.info(f"Usuario {user_id} salio de room {room}")
        
        except Exception as e:
            logger.error(f"Error leaving room: {e}")

    async def get_room_participants(self, room_id: int) -> List[dict]:
        """Obtiene la lista de participantes en el room con datos completos de la DB"""
        from app.db.models import Player, Room  # Import aquí para evitar circular imports
        
        participants = []

        db: Session = self.db_factory()
        
        try:
            # Obtener todos los jugadores conectados a esta room desde memoria
            connected_user_ids = [
                session_data['user_id'] 
                for sid, session_data in self.user_sessions.items() 
                if session_data.get('room_id') == room_id
            ]

            # DEBUG
            logger.info(f"🔍 Connected user_ids for room {room_id}: {connected_user_ids}")
            
            if not connected_user_ids:
                return []
            
            # Consultar la DB para obtener info completa de los jugadores
            players = db.query(Player).filter(
                Player.id.in_(connected_user_ids),
                Player.id_room == room_id
            ).all()

            # DEBUG
            logger.info(f"🔍 Players found in DB: {[p.id for p in players]}")
            
            # Construir la lista de participantes con formato correcto
            for player in players:
                participants.append({
                    'id': player.id,
                    'name': player.name,
                    'avatar': player.avatar_src,
                    'is_host': player.is_host,
                    'order': player.order,
                    'connected_at': next(
                        (s['connected_at'] for s in self.user_sessions.values() 
                         if s.get('user_id') == player.id and s.get('room_id') == room_id),
                        datetime.now().isoformat()
                    )
                })
            
            # Ordenar por order
            participants.sort(key=lambda x: x.get('order') if x.get('order') is not None else 999)
            
            logger.debug(f"Participants in room {room_id}: {participants}")
            return participants
            
        except Exception as e:
            logger.error(f"Error getting room participants: {e}")
            return []
        finally:
            db.close()

    # Metodos para las notificaciones

    async def emit_to_room(self, room_id: int, event: str, data: Dict):
        """Emite un evento a todos los jugadores en una partida"""
        room = self.get_room_name(room_id) # Tomo a que partida le mando la notificacion
        # Chequeo que la room no este vacia
        if not any(s['room_id'] == room_id for s in self.user_sessions.values()):
          logger.warning(f"La room esta vacía: {room}")
          return
        
        await self.sio.emit(event, data, room=room)
    
    async def emit_to_sid(self, sid: str, event: str, data: Dict):
        """Emite un evento privado a un jugador"""
        await self.sio.emit(event, data, to=sid)
    
    def get_sids_in_game(self, room_id: int) -> List[str]:
        sids = [sid for sid, s in self.user_sessions.items() if s.get('room_id') == room_id]
        logger.debug(f"get_sids_in_game({room_id}): user_sessions={self.user_sessions}, sids={sids}")
        return sids
    
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

def init_ws_manager(sio: socketio.AsyncServer, db_factory) -> WebSocketManager:
    global _ws_manager
    _ws_manager = WebSocketManager(sio, db_factory)
    return _ws_manager

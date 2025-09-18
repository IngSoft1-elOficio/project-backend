# sockets/socket_events.py
from .socket_manager import init_ws_manager, get_ws_manager
import socketio
import logging

logger = logging.getLogger(__name__)

def register_events(sio: socketio.AsyncServer):
    """Registra todos los eventos de socketIO"""

    # inicializar manager
    ws_manager = init_ws_manager(sio)

    @sio.event
    async def connect(sid, environ):
        """Maneja nuevas conexiones"""
        try:
            # implementar: validar conexion

            # guardar en session de socketIO
            await sio.save_session(sid, {'user_id': user_id})

            logger.info(f"Usuario {user_id} conectado con sid {sid}")

            # notificar conexion al cliente 
            await sio.emit('connected', {
                'message': 'Conectado existosamente',
                'user_id': user_id
            }, room=sid)

            return True
        except Exception as e:
            logger.error(f"Error en connect: {e}")
            await sio.disconnect(sid)
            return False
    
    @sio.event
    async def disconnect(sid):
        """maneja desconeciones"""
        try: 
            # obtener datos de session
            session = await sio.get_session(sid, default={})
            user_id = session.get('user_id')

            logger.info(f"Usuario {user_id} desconectado (sid: {sid})")
            # salir del room si estaba en uno
            await ws_manager.leave_game_room(sid)

        except Exception as e:
            logger.error(f"Error en disconnect: {e}")

    @sio.event
    async def join_game(sid, data):
        """Evento para unirse a una partida"""
        try:
            # validar datos

            # obtener datos de session
            session = await sio.get_session(sid)
            user_id = session.get('user_id')

            # unirse al room
            success = await ws_manager.join_game_room(sid, game_id, user_id)

            if success:
                await sio.emit('joined_game', {
                    'game_id': game_id,
                    'message': f'Te uniste a la partida {game_id}'
                }, room=sid)
        
        except Exception as e:
            logger.error(f"Error en join_game: {e}")
            await sio.emit('error',
                        {'message': 'Error uniendose a la partida'},
            room = sid)
    
    @sio.event
    async def get_room_status(sid, data):
        """Obtener datos de room (testing)"""
        try: 
            if not data or 'game_id' not in data:
                await sio.emit('error',
                               {'message': 'game_id requerido'},
                               room=sid)
                return

            game_id=data['game_id']
            participants = await ws_manager.get_room_participants(game_id)
            await sio.emit('room_status', {
                'game_id': game_id,
                'participants_count': len(participants),
                'participants': participants
            }, room=sid)

        except Exception as e:
            logger.error(f"Error en get_room_status: {e}")
        

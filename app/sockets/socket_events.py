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
            headers = environ.get('HTTP_USER_ID')
            user_id = int(headers)

            await sio.save_session(sid,{ 'user_id': user_id })

            # notificar conexion al cliente 
            await sio.emit('connected', {
                'message': 'Conectado existosamente'
            }, room=sid)

            logger.info(f"Conectado (sid: {sid})")

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
            session = await sio.get_session(sid)

            logger.info(f"Desconectado (sid: {sid})")
            
            # salir del room si estaba en uno
            await ws_manager.leave_game_room(sid)

        except Exception as e:
            logger.error(f"Error en disconnect: {e}")        

    @sio.event
    async def join_game(sid, data):
        """Evento de unirse a partida, solo para testing luego de implementar endpoint POST eliminar"""
        try:
            game_id = data['game_id']
            user_id = data['user_id']

            result = await ws_manager.join_game_room(sid, game_id,user_id)
             
        except Exception as e:
            logger.error(f"Error in join_game event: {e}")
            await sio.emit('join_error', {'message': 'Error joining game'}, room=sid)


    @sio.event
    async def get_participants(sid, data):
        """Evento para traer participantes del room (testing)"""
        try:
            game_id = data['game_id']

            result = await ws_manager.get_room_participants(game_id)
            print(f"result participants: {result}")
        
        except Exception as e:
            logger.error(f"Error in join_game event: {e}")
            await sio.emit('join_error', {'message': 'Error joining game'}, room=sid)
            
        # notificar conexion al cliente 
        await sio.emit('get_participants', {
            'participants_list': result
        }, room=sid)


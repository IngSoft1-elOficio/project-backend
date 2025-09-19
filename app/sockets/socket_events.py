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
            user_id = 123

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

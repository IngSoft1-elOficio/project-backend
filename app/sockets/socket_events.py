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
            # Debug logging
            logger.info(f"=== NEW CONNECTION ATTEMPT ===")
            logger.info(f"SID: {sid}")
            logger.info(f"Query string: {environ.get('QUERY_STRING', 'None')}")
            
            # Parse query parameters
            query_string = environ.get('QUERY_STRING', '')
            from urllib.parse import parse_qs
            query_params = parse_qs(query_string)
            
            logger.info(f"Parsed query params: {query_params}")
            
            # Get user_id from query params
            user_id_list = query_params.get('user_id', [])
            if not user_id_list:
                logger.error(f"❌ Missing user_id in query for sid: {sid}")
                await sio.emit('error', {'message': 'user_id required'}, room=sid)
                return False
                
            try:
                user_id = int(user_id_list[0])
            except (ValueError, IndexError):
                logger.error(f"❌ Invalid user_id format: {user_id_list}")
                await sio.emit('error', {'message': 'invalid user_id format'}, room=sid)
                return False
            
            # Get game_id from query params
            game_id_list = query_params.get('game_id', [])
            if not game_id_list:
                logger.error(f"❌ Missing game_id in query for sid: {sid}")
                await sio.emit('error', {'message': 'game_id required'}, room=sid)
                return False
                
            try:
                game_id = int(game_id_list[0])
            except (ValueError, IndexError):
                logger.error(f"❌ Invalid game_id format: {game_id_list}")
                await sio.emit('error', {'message': 'invalid game_id format'}, room=sid)
                return False
            
            logger.info(f"Extracted - SID: {sid}, Game ID: {game_id}, User ID: {user_id}")
            
            # Guardar session con toda la información
            await sio.save_session(sid, {
                'user_id': user_id,
                'game_id': game_id
            })
            
            logger.info(f"🚪 Attempting to join room for game {game_id}")
            # Usar ws_manager para unirse al room automáticamente
            success = await ws_manager.join_game_room(sid, game_id, user_id)
            
            if success:
                # Notificar conexión exitosa al cliente
                await sio.emit('connected', {
                    'message': 'Conectado exitosamente',
                    'user_id': user_id,
                    'game_id': game_id,
                    'sid': sid
                }, room=sid)
                
                logger.info(f"✅ User {user_id} connected successfully to game {game_id} (sid: {sid})")
                return True
            else:
                logger.error(f"❌ Failed to join user {user_id} to game {game_id}")
                await sio.emit('error', {'message': 'Failed to join game room'}, room=sid)
                return False
            
        except Exception as e:
            logger.error(f"❌ Unexpected error in connect: {e}")
            await sio.emit('error', {'message': f'Connection error: {str(e)}'}, room=sid)
            return False

    @sio.event
    async def disconnect(sid):
        """Maneja desconecciones"""
        try:
            # Obtener datos de sesión
            session = await sio.get_session(sid)
            user_id = session.get('user_id', 'Unknown') if session else 'Unknown'
            game_id = session.get('game_id', 'Unknown') if session else 'Unknown'
            
            logger.info(f"Usuario {user_id} desconectado de juego {game_id} (sid: {sid})")
            
            # Salir del room si estaba en uno
            if session and 'game_id' in session:
                await ws_manager.leave_game_room(sid, session['game_id'])
                
                # Notificar a otros jugadores en el room
                await sio.emit('player_disconnected', {
                    'user_id': user_id,
                    'message': f'Jugador {user_id} se desconectó'
                }, room=f"game_{session['game_id']}")
            
        except Exception as e:
            logger.error(f"Error en disconnect para sid {sid}: {e}")       

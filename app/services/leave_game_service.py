from sqlalchemy.orm import Session
from app.db.models import Room, Player, RoomStatus
from app.sockets.socket_service import get_websocket_service
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def leave_game_logic(db: Session, room_id: int, user_id: int):
    """
    Lógica para cancelar (host) o abandonar (jugador) una partida en estado WAITING.
    
    Args:
        db: Database session
        room_id: ID de la sala
        user_id: ID del jugador que hace la solicitud
        
    Returns:
        Dict con success, error, message, is_host
    """
    try:
        # 1. Validar que la sala existe
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            logger.warning(f"Room {room_id} not found")
            return {"success": False, "error": "room_not_found"}
        
        # 2. Validar que la sala está en estado WAITING
        if room.status != RoomStatus.WAITING:
            logger.warning(f"Room {room_id} is not in WAITING state (status: {room.status})")
            return {"success": False, "error": "game_already_started"}
        
        # 3. Buscar al jugador y validar que pertenece a la sala
        player = db.query(Player).filter(
            Player.id == user_id,
            Player.id_room == room_id
        ).first()
        
        if not player:
            logger.warning(f"Player {user_id} does not belong to room {room_id}")
            return {"success": False, "error": "player_not_in_room"}
        
        ws_service = get_websocket_service()
        
        # 4. Determinar si es host o jugador regular
        if player.is_host:
            # HOST: Cancelar partida completa
            logger.info(f"Host {user_id} is cancelling room {room_id}")
            
            # Desvincular TODOS los jugadores de la sala
            db.query(Player).filter(Player.id_room == room_id).update(
                {"id_room": None, "is_host": False, "order": None},
                synchronize_session=False
            )
            
            # Eliminar la sala
            db.delete(room)
            db.commit()
            
            logger.info(f"Room {room_id} deleted and all players unlinked")
            
            # Emitir evento WebSocket: game_cancelled
            await ws_service.notificar_game_cancelled(
                room_id=room_id,
                timestamp=datetime.now().isoformat()
            )
            
            return {
                "success": True,
                "message": "Game cancelled successfully",
                "is_host": True,
                "error": None
            }
        
        else:
            # JUGADOR: Abandonar partida
            logger.info(f"Player {user_id} is leaving room {room_id}")
            
            # Desvincular solo al jugador que abandona
            player.id_room = None
            player.order = None
            db.commit()
            
            # Obtener jugadores restantes para enviar en el evento
            remaining_players = db.query(Player).filter(Player.id_room == room_id).all()
            players_count = len(remaining_players)
            
            # Serializar jugadores para el evento
            players_data = [
                {
                    "id": p.id,
                    "name": p.name,
                    "avatar": p.avatar_src,
                    "is_host": p.is_host,
                    "order": p.order
                }
                for p in remaining_players
            ]

            logger.info(f"Player {user_id} left room {room_id}. {players_count} players remaining")
            
            # Emitir evento WebSocket: player_left
            await ws_service.notificar_player_left(
                room_id=room_id,
                player_id=user_id,
                players_count=players_count,
                players=players_data,
                timestamp=datetime.now().isoformat()
            )
            
            return {
                "success": True,
                "message": "Player left successfully",
                "is_host": False,
                "error": None
            }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error in leave_game_logic: {e}")
        return {"success": False, "error": "internal_error"}
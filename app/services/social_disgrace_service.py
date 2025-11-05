"""
Servicio para manejar la lógica de desgracia social.
Un jugador entra en desgracia social cuando todos sus secretos están revelados.
"""
from sqlalchemy.orm import Session
from app.db import crud
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def check_player_social_disgrace_status(
    db: Session, 
    game_id: int, 
    player_id: int
) -> bool:
    """
    Verifica si un jugador debe estar en desgracia social.
    
    Un jugador está en desgracia social si:
    - Tiene al menos 1 secreto en SECRET_SET
    - TODOS sus secretos están revelados (hidden=False)
    
    Args:
        db: Sesión de base de datos
        game_id: ID del juego
        player_id: ID del jugador
        
    Returns:
        True si el jugador debe estar en desgracia social, False en caso contrario
    """
    try:
        # Obtener todos los secretos del jugador usando CRUD
        secrets = crud.get_player_secrets(db, game_id, player_id)
        
        # Si no tiene secretos, no está en desgracia social
        if not secrets:
            logger.debug(f"Player {player_id} has no secrets in game {game_id}")
            return False
        
        # Verificar si todos los secretos están revelados
        all_revealed = all(not secret.hidden for secret in secrets)
        
        logger.debug(
            f"Player {player_id} in game {game_id}: "
            f"{len(secrets)} secrets, all_revealed={all_revealed}"
        )
        
        return all_revealed
        
    except Exception as e:
        logger.error(f"Error checking social disgrace status: {e}")
        return False


def update_social_disgrace_status(
    db: Session, 
    game_id: int, 
    player_id: int
) -> Optional[Dict]:
    """
    Actualiza el estado de desgracia social de un jugador.
    
    - Si debe estar en desgracia y no está registrado: lo agrega
    - Si no debe estar en desgracia y está registrado: lo elimina
    
    Args:
        db: Sesión de base de datos
        game_id: ID del juego
        player_id: ID del jugador
        
    Returns:
        Dict con información del cambio si hubo alguno, None si no hubo cambios
        {
            "action": "entered" | "exited",
            "player_id": int,
            "player_name": str,
            "game_id": int
        }
    """
    try:
        # Verificar si el jugador debe estar en desgracia social
        should_be_in_disgrace = check_player_social_disgrace_status(db, game_id, player_id)
        
        # Verificar si el jugador está actualmente en desgracia social usando CRUD
        is_in_disgrace = crud.check_player_in_social_disgrace(db, game_id, player_id)
        
        # Obtener información del jugador para el mensaje usando CRUD
        player = crud.get_player_by_id(db, player_id)
        player_name = player.name if player else f"Player {player_id}"
        
        # Caso 1: Debe estar en desgracia pero no está registrado -> AGREGAR
        if should_be_in_disgrace and not is_in_disgrace:
            crud.add_player_to_social_disgrace(db, game_id, player_id)
            
            logger.info(f"✨ {player_name} (ID: {player_id}) entered social disgrace in game {game_id}")
            
            return {
                "action": "entered",
                "player_id": player_id,
                "player_name": player_name,
                "game_id": game_id
            }
        
        # Caso 2: No debe estar en desgracia pero está registrado -> ELIMINAR
        elif not should_be_in_disgrace and is_in_disgrace:
            crud.remove_player_from_social_disgrace(db, game_id, player_id)
            
            logger.info(f"🎉 {player_name} (ID: {player_id}) exited social disgrace in game {game_id}")
            
            return {
                "action": "exited",
                "player_id": player_id,
                "player_name": player_name,
                "game_id": game_id
            }
        
        # Sin cambios
        logger.debug(f"No changes in social disgrace status for player {player_id} in game {game_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error updating social disgrace status: {e}")
        db.rollback()
        return None


def get_players_in_social_disgrace(db: Session, game_id: int) -> List[Dict]:
    """
    Obtiene la lista de jugadores en desgracia social para una partida.
    
    Args:
        db: Sesión de base de datos
        game_id: ID del juego
        
    Returns:
        Lista de diccionarios con información de jugadores en desgracia social
        [
            {
                "player_id": int,
                "player_name": str,
                "avatar_src": str,
                "entered_at": str (ISO format)
            }
        ]
    """
    try:
        # Usar CRUD para obtener información completa con join
        disgrace_records = crud.get_players_in_social_disgrace_with_info(db, game_id)
        
        result = []
        for disgrace, player in disgrace_records:
            result.append({
                "player_id": player.id,
                "player_name": player.name,
                "avatar_src": player.avatar_src,
                "entered_at": disgrace.entered_at.isoformat()
            })
        
        logger.debug(f"Found {len(result)} players in social disgrace for game {game_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error getting players in social disgrace: {e}")
        return []


async def notify_social_disgrace_change(
    game_id: int,
    change_info: Optional[Dict]
):
    """
    Emite una notificación por WebSocket sobre cambios en desgracia social.
    
    Args:
        game_id: ID del juego
        change_info: Información del cambio (resultado de update_social_disgrace_status)
    """
    from app.sockets.socket_manager import get_ws_manager
    from app.db.database import SessionLocal
    
    try:
        ws_manager = get_ws_manager()
        db = SessionLocal()
        
        # Obtener el room_id para este game usando CRUD
        room = crud.get_room_by_game_id(db, game_id)
        if not room:
            logger.error(f"No room found for game {game_id}")
            return
        
        # Obtener lista actualizada de jugadores en desgracia social
        players_in_disgrace = get_players_in_social_disgrace(db, game_id)
        
        # Preparar el mensaje
        message = None
        if change_info:
            action = change_info["action"]
            player_name = change_info["player_name"]
            if action == "entered":
                message = f"{player_name} ha entrado en desgracia social"
            elif action == "exited":
                message = f"{player_name} ha salido de desgracia social"
        
        # Emitir por WebSocket
        await ws_manager.emit_to_room(
            room_id=room.id,
            event="social_disgrace_update",
            data={
                "game_id": game_id,
                "players_in_disgrace": players_in_disgrace,
                "message": message,
                "change": change_info
            }
        )
        
        logger.info(f"📡 Social disgrace update emitted for game {game_id}: {message}")
        
    except Exception as e:
        logger.error(f"Error notifying social disgrace change: {e}")
    finally:
        if 'db' in locals():
            db.close()

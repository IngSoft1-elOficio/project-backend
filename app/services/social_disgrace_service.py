"""
Servicio para manejar la lógica de desgracia social.
Un jugador entra en desgracia social cuando todos sus secretos están revelados.
"""
from sqlalchemy.orm import Session
import asyncio
from app.db import crud
import logging
from typing import List, Dict, Optional
from ..db.database import SessionLocal

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
        secrets = crud.get_player_secrets(db, game_id, player_id)
        
        if not secrets:
            logger.debug(f"Player {player_id} has no secrets in game {game_id}")
            return False # cambiar a true si consideramos sin secretos como desgracia
        
        all_revealed = all(not secret.hidden for secret in secrets)
        
        logger.debug(
            f"Player {player_id} in game {game_id}: "
            f"{len(secrets)} secrets, all_revealed={all_revealed}"
        ) 
        return all_revealed
        
    except Exception as e:
        logger.error(f"Error checking social disgrace status: {e}")
        return False


def update_social_disgrace_status_no_commit(
    db: Session, 
    game_id: int, 
    player_id: int
) -> Optional[Dict]:
    """
    Actualiza el estado de desgracia social de un jugador SIN hacer commit.
    """
    try:
        should_be_in_disgrace = check_player_social_disgrace_status(db, game_id, player_id)
        is_in_disgrace = crud.check_player_in_social_disgrace(db, game_id, player_id)
        
        player = crud.get_player_by_id(db, player_id)
        player_name = player.name if player else f"Player {player_id}"
        
        # Obtenemos el avatar_src y ponemos uno por defecto si no existe
        avatar_src = "./avatar1.jpg" # Avatar por defecto si 'player' es None o no tiene 'avatar_src'
        if player and hasattr(player, 'avatar_src') and player.avatar_src:
            avatar_src = player.avatar_src
            
        
        # Caso 1: Debe estar en desgracia pero no está registrado -> AGREGAR
        if should_be_in_disgrace and not is_in_disgrace:
            crud.add_player_to_social_disgrace(db, game_id, player_id)
            db.flush()  # Flush en lugar de commit
            
            logger.info(f"{player_name} (ID: {player_id}) entered social disgrace in game {game_id}")
            
            return {
                "action": "entered",
                "player_id": player_id,
                "player_name": player_name,
                "avatar_src": avatar_src, # <-- AÑADIDO
                "game_id": game_id
            }
        
        # Caso 2: No debe estar en desgracia pero está registrado -> ELIMINAR
        elif not should_be_in_disgrace and is_in_disgrace:
            crud.remove_player_from_social_disgrace(db, game_id, player_id)
            db.flush()  # Flush en lugar de commit
            
            logger.info(f"{player_name} (ID: {player_id}) exited social disgrace in game {game_id}")
            
            return {
                "action": "exited",
                "player_id": player_id,
                "player_name": player_name,
                "avatar_src": avatar_src, # <-- AÑADIDO
                "game_id": game_id
            }
        
        # Sin cambios
        logger.debug(f"No changes in social disgrace status for player {player_id} in game {game_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error updating social disgrace status (no commit): {e}")
        return None


def update_social_disgrace_status(
    db: Session, 
    game_id: int, 
    player_id: int
) -> Optional[Dict]:
    """
    Actualiza el estado de desgracia social de un jugador CON commit.
    
    Esta función hace commit y debe usarse cuando se llama directamente desde un endpoint
    o servicio que maneja su propia transacción.
    
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
        change_info = update_social_disgrace_status_no_commit(db, game_id, player_id)
        
        if change_info:
            db.commit()  # Commit solo si hubo cambios
            
        return change_info
        
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
        # crud.get_players_in_social_disgrace_with_info ahora retorna directamente diccionarios
        disgrace_records = crud.get_players_in_social_disgrace_with_info(db, game_id)
        
        # Convertir entered_at a formato ISO
        result = []
        for record in disgrace_records:
            result.append({
                "player_id": record["player_id"],
                "player_name": record["player_name"],
                "avatar_src": record["avatar_src"],
                "entered_at": record["entered_at"].isoformat()
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
    """
    logger.warning(f"DEBUG: 5. ¡'notify_social_disgrace_change' FUE LLAMADO para game_id {game_id}!")
    
    from app.sockets.socket_service import get_websocket_service
    from app.db.database import SessionLocal
    
    db = SessionLocal() # Abrimos sesión UNA SOLA VEZ
    local_room_id = None # <-- Variable local para el ID
    
    try:
        # 1. Obtenemos el room y guardamos su ID en una variable simple
        room = crud.get_room_by_game_id(db, game_id)
        if not room:
            logger.error(f"DEBUG: 5a. NO SE ENCONTRÓ ROOM para game {game_id}")
            return
        
        local_room_id = room.id # <-- ¡SOLUCIÓN AL CRASH!
        logger.warning(f"DEBUG: 5b. Room ID {local_room_id} obtenido.")
        
        # 2. Sincronizamos la sesión
        db.commit() 
        logger.warning("DEBUG: 6a. (Nueva Sesión) Commit inicial hecho para sincronizar.")
        
        # 3. Consultamos la lista
        players_in_disgrace = get_players_in_social_disgrace(db, game_id)
        
        # 4. Si sigue vacía, re-intentamos (esto es por el race condition)
        if not players_in_disgrace and change_info and change_info.get("action") == "entered":
            logger.warning(f"DEBUG: 6b. AÚN vacía. (Race Condition). Esperando 200ms y re-sincronizando...")
            await asyncio.sleep(0.2)
            db.commit() # Re-sincronizamos
            players_in_disgrace = get_players_in_social_disgrace(db, game_id)
            logger.warning(f"DEBUG: 6c. Segunda consulta (post-sleep) devolvió: {players_in_disgrace}")
        
        ws_service = get_websocket_service()
        
        # 5. Usamos la variable local 'local_room_id'
        logger.warning(f"DEBUG: 6. Emitiendo 'social_disgrace_update' a room_id {local_room_id}...")
        
        await ws_service.notificar_social_disgrace_update(
            room_id=local_room_id, # <-- USAMOS LA VARIABLE LOCAL
            game_id=game_id,
            players_in_disgrace=players_in_disgrace, 
            change_info=change_info
        )
        
        logger.warning("DEBUG: 7. EMISIÓN COMPLETA.")
        
    except Exception as e:
        logger.error(f"Error notifying social disgrace change: {e}", exc_info=True)
    finally:
        if 'db' in locals() and db.is_active:
             logger.warning("DEBUG: 8. Cerrando sesión final.")
             db.close()


async def check_and_notify_social_disgrace(game_id: int, player_id: int):
    """
    CREA UNA SESIÓN NUEVA, comprueba el estado de un jugador,
    y notifica si hay cambios.
    Esta es la forma SEGURA de llamarlo desde un endpoint
    después de un commit, ya que evita datos "rancios" (stale data).
    """
    logger.warning(f"DEBUG (check_and_notify): Iniciando chequeo para player {player_id} en game {game_id} (SESIÓN NUEVA)")
    db = SessionLocal()  # Crea una sesion limpia
    try:
        db.commit()
        logger.warning("DEBUG (check_and_notify): 'commit' inicial (sync) HECHO.")
        # Usamos la función con commit
        change_info = update_social_disgrace_status(
            db=db,
            game_id=game_id,
            player_id=player_id
        )
        
        logger.warning(f"DEBUG (check_and_notify): 'update_social_disgrace_status' (sesión limpia) devolvió: {change_info}")
        db.expire_all()

        from ..services.game_service import win_for_total_disgrace
        game_has_ended = await win_for_total_disgrace(db=db, game_id=game_id)
        
        # Si el juego termino, no envia notificacion de "desgracia social",
        if game_has_ended:
            logger.warning(f"DEBUG (check_and_notify): Juego terminado por TOTAL_DISGRACE. No se enviará 'social_disgrace_update'.")
            return

        # Si el juego no termino --> verifica si hay un cambio y notifica
        if change_info:
            logger.warning(f"DEBUG (check_and_notify): Hubo cambio, llamando a notify...")
            # Esta función (notify...) también crea su propia sesion
            await notify_social_disgrace_change(
                game_id=game_id,
                change_info=change_info
            )
        else:
            logger.warning(f"DEBUG (check_and_notify): No hubo cambios.")

    except Exception as e:
        logger.error(f"Error en check_and_notify_social_disgrace: {e}", exc_info=True)
    finally:
        db.close() # Cierra la sesion limpia

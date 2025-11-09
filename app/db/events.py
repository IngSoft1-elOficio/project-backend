"""
Event listeners para SQLAlchemy.
Maneja automáticamente los cambios en CardsXGame para detectar 
cuándo un jugador entra o sale de desgracia social.
"""
from sqlalchemy import event
from sqlalchemy.orm import Session
from app.db.models import CardsXGame, CardState
import logging
import asyncio
import os

logger = logging.getLogger(__name__)


def _events_enabled() -> bool:
    """
    Verifica si los eventos están habilitados.
    Se evalúa cada vez (lazy) para permitir que conftest.py establezca la variable antes.
    """
    return os.getenv("DISABLE_DB_EVENTS", "false").lower() != "true"


def _should_check_social_disgrace(target: CardsXGame) -> bool:
    """
    Determina si un cambio en CardsXGame debe disparar verificación de desgracia social.
    Solo nos interesa si la carta es un secreto (is_in == SECRET_SET).
    """
    return target.is_in == CardState.SECRET_SET and target.player_id is not None


def _run_async_task(coro):
    """
    Helper para ejecutar una coroutine de forma segura en el event loop.
    
    - Si ya hay un loop corriendo (FastAPI), usa create_task
    - Si no hay loop, ejecuta la coroutine en un loop temporal
    
    Esto evita fugas de loops y mantiene compatibilidad con FastAPI.
    """
    try:
        loop = asyncio.get_running_loop()
        # Hay un loop activo, crear la tarea en él
        loop.create_task(coro)
    except RuntimeError:
        # No hay loop activo, ejecutar de forma temporal
        # Esto puede pasar en tests o contextos síncronos
        asyncio.run(coro)


def _handle_social_disgrace_check(target: CardsXGame):
    """
    Maneja la verificación de desgracia social después de un cambio en CardsXGame.
    
    IMPORTANTE: Esta función ahora crea su PROPIA sesión de DB para evitar
    conflictos de 'Session is already flushing' con el listener de SQLAlchemy.
    """
    # Saltar si los eventos están deshabilitados (ej: durante tests)
    if not _events_enabled():
        return
    
    # Import aquí para evitar circular imports
    from app.services.social_disgrace_service import (
        update_social_disgrace_status, # <-- CAMBIADO: Usamos la función CON commit
        notify_social_disgrace_change
    )
    from app.db.database import SessionLocal # <-- AÑADIDO: Importamos SessionLocal
    
    if not _should_check_social_disgrace(target):
        return
    
    logger.warning("DEBUG: 2c. Creando nueva sesión (SessionLocal) para desgracia social...") # <-- LOG DE DEBUG NUEVO
    
    db = SessionLocal() # <-- AÑADIDO: Creamos una sesión nueva e independiente
    try:
        # Actualizar el estado de desgracia social CON commit, usando la nueva sesión
        change_info = update_social_disgrace_status( # <-- CAMBIADO: Usamos la función CON commit
            db=db,
            game_id=target.id_game,
            player_id=target.player_id
        )
        
        logger.warning(f"DEBUG: 3. (En nueva sesión) 'update_social_disgrace_status' devolvió: {change_info}") # <-- LOG DE DEBUG MEJORADO
        
        # Si hubo un cambio, programar notificación por WebSocket (operación asíncrona)
        if change_info:
            logger.warning("DEBUG: 4. (En nueva sesión) ¡HUBO CAMBIO! Llamando a _run_async_task(notify_social_disgrace_change)...") # <-- LOG DE DEBUG MEJORADO
            _run_async_task(
                notify_social_disgrace_change(
                    game_id=target.id_game,
                    change_info=change_info
                )
            )
        else:
             logger.warning("DEBUG: 4a. (En nueva sesión) NO HUBO CAMBIO. No se emite evento.") # <-- LOG DE DEBUG MEJORADO
            
    except Exception as e:
        logger.error(f"Error handling social disgrace check (con sesión propia): {e}", exc_info=True)
    finally:
        logger.warning("DEBUG: 8. Cerrando sesión (SessionLocal) de desgracia social.") # <-- LOG DE DEBUG NUEVO
        db.close() # <-- AÑADIDO: Cerramos la sesión


@event.listens_for(CardsXGame, 'after_update')
def after_update_cards_x_game(mapper, connection, target):
    """
    Event listener que se dispara después de actualizar un registro en CardsXGame.
    
    Este es el caso más común: cuando se revela u oculta un secreto (cambio en 'hidden').
    """
    logger.warning(f"DEBUG: 1. 'after_update_cards_x_game' DISPARADO para game={target.id_game}, card={target.id_card}, hidden={target.hidden}")
    
    # Saltar si los eventos están deshabilitados (ej: durante tests)
    if not _events_enabled():
        return
    
    # YA NO INTENTAMOS OBTENER LA SESIÓN AQUÍ
    # session = Session.object_session(target) <-- ELIMINADO
    # if session is None: <-- ELIMINADO
    #     logger.warning("No session available for social disgrace check after update") <-- ELIMINADO
    #     return <-- ELIMINADO
    
    logger.warning(f"DEBUG: 1c. 'after_update_cards_x_game' - Llamando a _handle_social_disgrace_check...")
    
    _handle_social_disgrace_check(target) # <-- CAMBIADO: Ya no pasamos la sesión


@event.listens_for(CardsXGame, 'after_insert')
def after_insert_cards_x_game(mapper, connection, target):
    """
    Event listener que se dispara después de insertar un registro en CardsXGame.
    
    Aunque es menos común, podría darse el caso de que se inserte un secreto ya revelado.
    """
    # Saltar si los eventos están deshabilitados (ej: durante tests)
    if not _events_enabled():
        return
    
    # YA NO INTENTAMOS OBTENER LA SESIÓN AQUÍ
    # session = Session.object_session(target) <-- ELIMINADO
    # if session is None: <-- ELIMINADO
    #     logger.warning("No session available for social disgrace check after insert") <-- ELIMINADO
    #     return <-- ELIMINADO
    
    logger.warning(f"🔔 CardsXGame inserted: game={target.id_game}, player={target.player_id}, is_in={target.is_in}, hidden={target.hidden}")
    
    _handle_social_disgrace_check(target) # <-- CAMBIADO: Ya no pasamos la sesión


@event.listens_for(CardsXGame, 'after_delete')
def after_delete_cards_x_game(mapper, connection, target):
    """
    Event listener que se dispara después de eliminar un registro en CardsXGame.
    
    Si se elimina un secreto de un jugador, podría salir de desgracia social.
    """
    # Saltar si los eventos están deshabilitados (ej: durante tests)
    if not _events_enabled():
        return
    
    # Import aquí para evitar circular imports
    from app.db.database import SessionLocal
    from app.services.social_disgrace_service import (
        update_social_disgrace_status,
        notify_social_disgrace_change
    )
    
    logger.debug(f"🔔 CardsXGame deleted: game={target.id_game}, "
                f"player={target.player_id}, card={target.id_card}, "
                f"is_in={target.is_in}")
    
    if not _should_check_social_disgrace(target):
        return
    
    # Para DELETE necesitamos crear una nueva sesión ya que el objeto 
    # está siendo eliminado y no tiene sesión válida
    db = SessionLocal()
    try:
        change_info = update_social_disgrace_status(
            db=db,
            game_id=target.id_game,
            player_id=target.player_id
        )
        
        if change_info:
            _run_async_task(
                notify_social_disgrace_change(
                    game_id=target.id_game,
                    change_info=change_info
                )
            )
    except Exception as e:
        logger.error(f"Error handling social disgrace check on delete: {e}", exc_info=True)
    finally:
        db.close()


def register_events():
    """
    Función helper para registrar todos los eventos.
    Puede ser llamada desde database.py o main.py para asegurar que los listeners
    estén registrados.
    """
    print(f"\n✅ Social disgrace event listeners registered")
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


def _handle_social_disgrace_check(session: Session, target: CardsXGame):
    """
    Maneja la verificación de desgracia social después de un cambio en CardsXGame.
    Esta función se ejecuta de forma síncrona en el contexto de SQLAlchemy.
    
    IMPORTANTE: NO hace commit, solo flush. El commit debe ser manejado por quien
    inició la transacción original (el endpoint).
    """
    # Saltar si los eventos están deshabilitados (ej: durante tests)
    if not _events_enabled():
        return
    
    # Import aquí para evitar circular imports
    # (events.py -> service -> models -> database -> events)
    from app.services.social_disgrace_service import (
        update_social_disgrace_status_no_commit,
        notify_social_disgrace_change
    )
    
    if not _should_check_social_disgrace(target):
        return
    
    try:
        # Actualizar el estado de desgracia social SIN commit
        # El commit lo hará la transacción padre
        change_info = update_social_disgrace_status_no_commit(
            db=session,
            game_id=target.id_game,
            player_id=target.player_id
        )
        
        # Si hubo un cambio, programar notificación por WebSocket (operación asíncrona)
        if change_info:
            _run_async_task(
                notify_social_disgrace_change(
                    game_id=target.id_game,
                    change_info=change_info
                )
            )
            
    except Exception as e:
        logger.error(f"Error handling social disgrace check: {e}", exc_info=True)


@event.listens_for(CardsXGame, 'after_update')
def after_update_cards_x_game(mapper, connection, target):
    """
    Event listener que se dispara después de actualizar un registro en CardsXGame.
    
    Este es el caso más común: cuando se revela u oculta un secreto (cambio en 'hidden').
    """
    # Saltar si los eventos están deshabilitados (ej: durante tests)
    if not _events_enabled():
        return
    
    session = Session.object_session(target)
    if session is None:
        logger.warning("No session available for social disgrace check after update")
        return
    
    logger.debug(f"🔔 CardsXGame updated: game={target.id_game}, "
                f"player={target.player_id}, card={target.id_card}, "
                f"is_in={target.is_in}, hidden={target.hidden}")
    
    _handle_social_disgrace_check(session, target)


@event.listens_for(CardsXGame, 'after_insert')
def after_insert_cards_x_game(mapper, connection, target):
    """
    Event listener que se dispara después de insertar un registro en CardsXGame.
    
    Aunque es menos común, podría darse el caso de que se inserte un secreto ya revelado.
    """
    # Saltar si los eventos están deshabilitados (ej: durante tests)
    if not _events_enabled():
        return
    
    session = Session.object_session(target)
    if session is None:
        logger.warning("No session available for social disgrace check after insert")
        return
    
    logger.debug(f"🔔 CardsXGame inserted: game={target.id_game}, "
                f"player={target.player_id}, card={target.id_card}, "
                f"is_in={target.is_in}, hidden={target.hidden}")
    
    _handle_social_disgrace_check(session, target)


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
    logger.info("✅ Social disgrace event listeners registered")

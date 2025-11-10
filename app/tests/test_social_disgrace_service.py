"""
Tests para el servicio de desgracia social (social_disgrace_service.py).
Cubre las funciones de verificación, actualización y consulta de desgracia social.
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from app.services import social_disgrace_service
from app.db import crud, models


@pytest.fixture
def db_session():
    """Fixture para sesión de base de datos mockeada"""
    return MagicMock()


@pytest.fixture
def sample_secrets_all_revealed():
    """Fixture con todos los secretos revelados (hidden=False)"""
    secrets = []
    for i in range(3):
        secret = MagicMock(spec=models.CardsXGame)
        secret.hidden = False
        secret.id = i + 1
        secrets.append(secret)
    return secrets


@pytest.fixture
def sample_secrets_mixed():
    """Fixture con secretos mixtos (algunos revelados, otros ocultos)"""
    secrets = []
    for i in range(3):
        secret = MagicMock(spec=models.CardsXGame)
        secret.hidden = (i == 0)  # Solo el primero está oculto
        secret.id = i + 1
        secrets.append(secret)
    return secrets


@pytest.fixture
def sample_player():
    """Fixture para un jugador de prueba"""
    player = MagicMock(spec=models.Player)
    player.id = 5
    player.name = "Ana"
    player.avatar_src = "avatar.png"
    return player


# ===============================
# check_player_social_disgrace_status
# ===============================

def test_check_player_social_disgrace_status_all_revealed(db_session, sample_secrets_all_revealed):
    """Test: jugador con todos sus secretos revelados está en desgracia"""
    with patch.object(crud, 'get_player_secrets', return_value=sample_secrets_all_revealed):
        result = social_disgrace_service.check_player_social_disgrace_status(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    assert result is True


def test_check_player_social_disgrace_status_mixed(db_session, sample_secrets_mixed):
    """Test: jugador con secretos mixtos NO está en desgracia"""
    with patch.object(crud, 'get_player_secrets', return_value=sample_secrets_mixed):
        result = social_disgrace_service.check_player_social_disgrace_status(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    assert result is False


def test_check_player_social_disgrace_status_no_secrets(db_session):
    """Test: jugador sin secretos NO está en desgracia"""
    with patch.object(crud, 'get_player_secrets', return_value=[]):
        result = social_disgrace_service.check_player_social_disgrace_status(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    assert result is False


def test_check_player_social_disgrace_status_all_hidden(db_session):
    """Test: jugador con todos los secretos ocultos NO está en desgracia"""
    secrets = []
    for i in range(3):
        secret = MagicMock(spec=models.CardsXGame)
        secret.hidden = True
        secrets.append(secret)
    
    with patch.object(crud, 'get_player_secrets', return_value=secrets):
        result = social_disgrace_service.check_player_social_disgrace_status(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    assert result is False


def test_check_player_social_disgrace_status_exception(db_session):
    """Test: excepción durante verificación retorna False"""
    with patch.object(crud, 'get_player_secrets', side_effect=Exception("DB Error")):
        result = social_disgrace_service.check_player_social_disgrace_status(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    assert result is False


# ===============================
# update_social_disgrace_status
# ===============================

def test_update_social_disgrace_status_player_enters_disgrace(db_session, sample_player):
    """Test: jugador entra en desgracia social"""
    with patch.object(social_disgrace_service, 'check_player_social_disgrace_status', return_value=True), \
         patch.object(crud, 'check_player_in_social_disgrace', return_value=False), \
         patch.object(crud, 'get_player_by_id', return_value=sample_player), \
         patch.object(crud, 'add_player_to_social_disgrace') as mock_add:
        
        result = social_disgrace_service.update_social_disgrace_status(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    assert result is not None
    assert result["action"] == "entered"
    assert result["player_id"] == 5
    assert result["player_name"] == "Ana"
    assert result["game_id"] == 1
    mock_add.assert_called_once_with(db_session, 1, 5)
    db_session.commit.assert_called_once()


def test_update_social_disgrace_status_player_exits_disgrace(db_session, sample_player):
    """Test: jugador sale de desgracia social"""
    with patch.object(social_disgrace_service, 'check_player_social_disgrace_status', return_value=False), \
         patch.object(crud, 'check_player_in_social_disgrace', return_value=True), \
         patch.object(crud, 'get_player_by_id', return_value=sample_player), \
         patch.object(crud, 'remove_player_from_social_disgrace') as mock_remove:
        
        result = social_disgrace_service.update_social_disgrace_status(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    assert result is not None
    assert result["action"] == "exited"
    assert result["player_id"] == 5
    assert result["player_name"] == "Ana"
    assert result["game_id"] == 1
    mock_remove.assert_called_once_with(db_session, 1, 5)
    db_session.commit.assert_called_once()


def test_update_social_disgrace_status_no_change_already_in(db_session, sample_player):
    """Test: jugador ya está en desgracia y debe seguir estando (sin cambios)"""
    with patch.object(social_disgrace_service, 'check_player_social_disgrace_status', return_value=True), \
         patch.object(crud, 'check_player_in_social_disgrace', return_value=True), \
         patch.object(crud, 'get_player_by_id', return_value=sample_player):
        
        result = social_disgrace_service.update_social_disgrace_status(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    assert result is None


def test_update_social_disgrace_status_no_change_not_in(db_session, sample_player):
    """Test: jugador NO está en desgracia y no debe estarlo (sin cambios)"""
    with patch.object(social_disgrace_service, 'check_player_social_disgrace_status', return_value=False), \
         patch.object(crud, 'check_player_in_social_disgrace', return_value=False), \
         patch.object(crud, 'get_player_by_id', return_value=sample_player):
        
        result = social_disgrace_service.update_social_disgrace_status(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    assert result is None


def test_update_social_disgrace_status_player_not_found(db_session):
    """Test: jugador no encontrado usa ID genérico"""
    with patch.object(social_disgrace_service, 'check_player_social_disgrace_status', return_value=True), \
         patch.object(crud, 'check_player_in_social_disgrace', return_value=False), \
         patch.object(crud, 'get_player_by_id', return_value=None), \
         patch.object(crud, 'add_player_to_social_disgrace'):
        
        result = social_disgrace_service.update_social_disgrace_status(
            db=db_session,
            game_id=1,
            player_id=99
        )
    
    assert result is not None
    assert result["player_name"] == "Player 99"


def test_update_social_disgrace_status_exception_on_enter(db_session, sample_player):
    """Test: excepción al intentar entrar en desgracia - manejo interno sin rollback"""
    with patch.object(social_disgrace_service, 'check_player_social_disgrace_status', return_value=True), \
         patch.object(crud, 'check_player_in_social_disgrace', return_value=False), \
         patch.object(crud, 'get_player_by_id', return_value=sample_player), \
         patch.object(crud, 'add_player_to_social_disgrace', side_effect=Exception("DB Error")):
        
        result = social_disgrace_service.update_social_disgrace_status(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    # La excepción ocurre en update_social_disgrace_status_no_commit que NO hace rollback
    # Solo retorna None. El rollback solo se hace si la excepción ocurre después del commit.
    assert result is None
    # No se llama rollback porque la excepción se maneja internamente
    db_session.rollback.assert_not_called()


def test_update_social_disgrace_status_exception_on_exit(db_session, sample_player):
    """Test: excepción al intentar salir de desgracia - manejo interno sin rollback"""
    with patch.object(social_disgrace_service, 'check_player_social_disgrace_status', return_value=False), \
         patch.object(crud, 'check_player_in_social_disgrace', return_value=True), \
         patch.object(crud, 'get_player_by_id', return_value=sample_player), \
         patch.object(crud, 'remove_player_from_social_disgrace', side_effect=Exception("DB Error")):
        
        result = social_disgrace_service.update_social_disgrace_status(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    # La excepción ocurre en update_social_disgrace_status_no_commit que NO hace rollback
    # Solo retorna None. El rollback solo se hace si la excepción ocurre después del commit.
    assert result is None
    # No se llama rollback porque la excepción se maneja internamente
    db_session.rollback.assert_not_called()


# ===============================
# get_players_in_social_disgrace
# ===============================

def test_get_players_in_social_disgrace_with_players(db_session):
    """Test: obtener lista de jugadores en desgracia con datos"""
    from datetime import datetime
    
    mock_records = [
        {
            "player_id": 1,
            "player_name": "Ana",
            "avatar_src": "avatar1.png",
            "entered_at": datetime(2025, 11, 6, 10, 30)
        },
        {
            "player_id": 2,
            "player_name": "Luis",
            "avatar_src": "avatar2.png",
            "entered_at": datetime(2025, 11, 6, 11, 45)
        }
    ]
    
    with patch.object(crud, 'get_players_in_social_disgrace_with_info', return_value=mock_records):
        result = social_disgrace_service.get_players_in_social_disgrace(
            db=db_session,
            game_id=1
        )
    
    assert len(result) == 2
    assert result[0]["player_id"] == 1
    assert result[0]["player_name"] == "Ana"
    assert result[0]["entered_at"] == "2025-11-06T10:30:00"
    assert result[1]["player_id"] == 2
    assert result[1]["player_name"] == "Luis"


def test_get_players_in_social_disgrace_empty_list(db_session):
    """Test: obtener lista vacía cuando nadie está en desgracia"""
    with patch.object(crud, 'get_players_in_social_disgrace_with_info', return_value=[]):
        result = social_disgrace_service.get_players_in_social_disgrace(
            db=db_session,
            game_id=1
        )
    
    assert result == []


def test_get_players_in_social_disgrace_exception(db_session):
    """Test: excepción al obtener lista retorna lista vacía"""
    with patch.object(crud, 'get_players_in_social_disgrace_with_info', side_effect=Exception("DB Error")):
        result = social_disgrace_service.get_players_in_social_disgrace(
            db=db_session,
            game_id=1
        )
    
    assert result == []


# ===============================
# notify_social_disgrace_change
# ===============================

@pytest.mark.asyncio
async def test_notify_social_disgrace_change_with_change_info():
    """Test: notificación con información de cambio"""
    from datetime import datetime
    
    mock_room = MagicMock(spec=models.Room)
    mock_room.id = 10
    
    mock_db = MagicMock()
    mock_db.close = MagicMock()
    
    change_info = {
        "action": "entered",
        "player_id": 5,
        "player_name": "Ana",
        "game_id": 1
    }
    
    disgrace_list = [
        {
            "player_id": 5,
            "player_name": "Ana",
            "avatar_src": "avatar.png",
            "entered_at": "2025-11-06T10:30:00"
        }
    ]
    
    mock_ws_service = MagicMock()
    mock_ws_service.notificar_social_disgrace_update = AsyncMock()
    
    with patch('app.db.database.SessionLocal', return_value=mock_db), \
         patch.object(crud, 'get_room_by_game_id', return_value=mock_room), \
         patch.object(social_disgrace_service, 'get_players_in_social_disgrace', return_value=disgrace_list), \
         patch('app.sockets.socket_service.get_websocket_service', return_value=mock_ws_service):
        
        await social_disgrace_service.notify_social_disgrace_change(
            game_id=1,
            change_info=change_info
        )
    
    mock_ws_service.notificar_social_disgrace_update.assert_awaited_once_with(
        room_id=10,
        game_id=1,
        players_in_disgrace=disgrace_list,
        change_info=change_info
    )
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_notify_social_disgrace_change_without_change_info():
    """Test: notificación sin información de cambio (actualización general)"""
    mock_room = MagicMock(spec=models.Room)
    mock_room.id = 20
    
    mock_db = MagicMock()
    mock_db.close = MagicMock()
    
    mock_ws_service = MagicMock()
    mock_ws_service.notificar_social_disgrace_update = AsyncMock()
    
    with patch('app.db.database.SessionLocal', return_value=mock_db), \
         patch.object(crud, 'get_room_by_game_id', return_value=mock_room), \
         patch.object(social_disgrace_service, 'get_players_in_social_disgrace', return_value=[]), \
         patch('app.sockets.socket_service.get_websocket_service', return_value=mock_ws_service):
        
        await social_disgrace_service.notify_social_disgrace_change(
            game_id=2,
            change_info=None
        )
    
    mock_ws_service.notificar_social_disgrace_update.assert_awaited_once_with(
        room_id=20,
        game_id=2,
        players_in_disgrace=[],
        change_info=None
    )


@pytest.mark.asyncio
async def test_notify_social_disgrace_change_room_not_found():
    """Test: notificación cuando no se encuentra el room"""
    mock_db = MagicMock()
    mock_db.close = MagicMock()
    
    with patch('app.db.database.SessionLocal', return_value=mock_db), \
         patch.object(crud, 'get_room_by_game_id', return_value=None):
        
        await social_disgrace_service.notify_social_disgrace_change(
            game_id=999,
            change_info=None
        )
    
    # Debe cerrar la DB aunque no haya room
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_notify_social_disgrace_change_exception():
    """Test: excepción durante notificación"""
    mock_db = MagicMock()
    mock_db.close = MagicMock()
    
    with patch('app.db.database.SessionLocal', return_value=mock_db), \
         patch.object(crud, 'get_room_by_game_id', side_effect=Exception("DB Error")):
        
        await social_disgrace_service.notify_social_disgrace_change(
            game_id=1,
            change_info=None
        )
    
    # Debe cerrar la DB incluso si hay excepción
    mock_db.close.assert_called_once()

def test_update_social_disgrace_status_no_commit_player_enters(db_session, sample_player):
    """Test: update_social_disgrace_status_no_commit cuando jugador entra en desgracia"""
    with patch.object(social_disgrace_service, 'check_player_social_disgrace_status', return_value=True), \
         patch.object(crud, 'check_player_in_social_disgrace', return_value=False), \
         patch.object(crud, 'get_player_by_id', return_value=sample_player), \
         patch.object(crud, 'add_player_to_social_disgrace') as mock_add:
        
        result = social_disgrace_service.update_social_disgrace_status_no_commit(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    assert result is not None
    assert result["action"] == "entered"
    assert result["player_id"] == 5
    assert result["player_name"] == "Ana"
    assert result["avatar_src"] == "avatar.png"
    mock_add.assert_called_once_with(db_session, 1, 5)
    db_session.flush.assert_called_once()


def test_update_social_disgrace_status_no_commit_default_avatar():
    """Test: usa avatar por defecto cuando player es None"""
    db_session = MagicMock()
    
    with patch.object(social_disgrace_service, 'check_player_social_disgrace_status', return_value=True), \
         patch.object(crud, 'check_player_in_social_disgrace', return_value=False), \
         patch.object(crud, 'get_player_by_id', return_value=None), \
         patch.object(crud, 'add_player_to_social_disgrace'):
        
        result = social_disgrace_service.update_social_disgrace_status_no_commit(
            db=db_session,
            game_id=1,
            player_id=99
        )
    
    assert result is not None
    assert result["avatar_src"] == "./avatar1.jpg"
    assert result["player_name"] == "Player 99"


def test_update_social_disgrace_status_no_commit_player_without_avatar():
    """Test: usa avatar por defecto cuando player no tiene avatar_src"""
    db_session = MagicMock()
    player = MagicMock(spec=models.Player)
    player.id = 5
    player.name = "Test"
    player.avatar_src = None  # Sin avatar
    
    with patch.object(social_disgrace_service, 'check_player_social_disgrace_status', return_value=True), \
         patch.object(crud, 'check_player_in_social_disgrace', return_value=False), \
         patch.object(crud, 'get_player_by_id', return_value=player), \
         patch.object(crud, 'add_player_to_social_disgrace'):
        
        result = social_disgrace_service.update_social_disgrace_status_no_commit(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    assert result is not None
    assert result["avatar_src"] == "./avatar1.jpg"


def test_update_social_disgrace_status_no_commit_player_exits(db_session, sample_player):
    """Test: update_social_disgrace_status_no_commit cuando jugador sale de desgracia"""
    with patch.object(social_disgrace_service, 'check_player_social_disgrace_status', return_value=False), \
         patch.object(crud, 'check_player_in_social_disgrace', return_value=True), \
         patch.object(crud, 'get_player_by_id', return_value=sample_player), \
         patch.object(crud, 'remove_player_from_social_disgrace') as mock_remove:
        
        result = social_disgrace_service.update_social_disgrace_status_no_commit(
            db=db_session,
            game_id=1,
            player_id=5
        )
    
    assert result is not None
    assert result["action"] == "exited"
    assert result["player_id"] == 5
    assert result["avatar_src"] == "avatar.png"
    mock_remove.assert_called_once_with(db_session, 1, 5)
    db_session.flush.assert_called_once()


# ===============================
# check_and_notify_social_disgrace
# ===============================

@pytest.mark.asyncio
async def test_check_and_notify_social_disgrace_with_change():
    """Test: check_and_notify cuando hay cambio en desgracia"""
    mock_db = MagicMock()
    
    change_info = {
        "action": "entered",
        "player_id": 5,
        "player_name": "Ana",
        "game_id": 1
    }
    
    mock_notify = AsyncMock()
    
    with patch('app.services.social_disgrace_service.SessionLocal', return_value=mock_db), \
         patch.object(social_disgrace_service, 'update_social_disgrace_status', return_value=change_info) as mock_update, \
         patch.object(social_disgrace_service, 'notify_social_disgrace_change', mock_notify):
        
        await social_disgrace_service.check_and_notify_social_disgrace(
            game_id=1,
            player_id=5
        )
    
    # Verificar que se llamó con la sesión correcta
    mock_update.assert_called_once_with(db=mock_db, game_id=1, player_id=5)
    
    # Verificar que se llamó notify con el change_info
    mock_notify.assert_awaited_once_with(game_id=1, change_info=change_info)
    
    # Verificar que se cerró la sesión
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_check_and_notify_social_disgrace_without_change():
    """Test: check_and_notify cuando NO hay cambio"""
    mock_db = MagicMock()
    
    mock_notify = AsyncMock()
    
    with patch('app.services.social_disgrace_service.SessionLocal', return_value=mock_db), \
         patch.object(social_disgrace_service, 'update_social_disgrace_status', return_value=None) as mock_update, \
         patch.object(social_disgrace_service, 'notify_social_disgrace_change', mock_notify):
        
        await social_disgrace_service.check_and_notify_social_disgrace(
            game_id=1,
            player_id=5
        )
    
    # Verificar que se llamó update
    mock_update.assert_called_once_with(db=mock_db, game_id=1, player_id=5)
    
    # Verificar que NO se llamó notify porque no hubo cambio
    mock_notify.assert_not_awaited()
    
    # Verificar que se cerró la sesión
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_check_and_notify_social_disgrace_exception():
    """Test: check_and_notify maneja excepciones correctamente"""
    mock_db = MagicMock()
    
    with patch('app.services.social_disgrace_service.SessionLocal', return_value=mock_db), \
         patch.object(social_disgrace_service, 'update_social_disgrace_status', side_effect=Exception("DB Error")):
        
        # No debe lanzar excepción
        await social_disgrace_service.check_and_notify_social_disgrace(
            game_id=1,
            player_id=5
        )
    
    # Debe cerrar la DB incluso con excepción
    mock_db.close.assert_called_once()


# ===============================
# notify_social_disgrace_change - RACE CONDITION
# ===============================

@pytest.mark.asyncio
async def test_notify_social_disgrace_change_race_condition_retry():
    """Test: retry cuando la lista está vacía por race condition"""
    mock_room = MagicMock(spec=models.Room)
    mock_room.id = 10
    
    mock_db = MagicMock()
    mock_db.close = MagicMock()
    mock_db.is_active = True
    
    change_info = {
        "action": "entered",
        "player_id": 5,
        "player_name": "Ana",
        "game_id": 1
    }
    
    # Primera llamada retorna vacío, segunda retorna con datos
    disgrace_list_final = [
        {
            "player_id": 5,
            "player_name": "Ana",
            "avatar_src": "avatar.png",
            "entered_at": "2025-11-06T10:30:00"
        }
    ]
    
    mock_ws_service = MagicMock()
    mock_ws_service.notificar_social_disgrace_update = AsyncMock()
    
    with patch('app.db.database.SessionLocal', return_value=mock_db), \
         patch.object(crud, 'get_room_by_game_id', return_value=mock_room), \
         patch.object(social_disgrace_service, 'get_players_in_social_disgrace', side_effect=[[], disgrace_list_final]) as mock_get, \
         patch('app.sockets.socket_service.get_websocket_service', return_value=mock_ws_service), \
         patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        
        await social_disgrace_service.notify_social_disgrace_change(
            game_id=1,
            change_info=change_info
        )
    
    # Debe llamar a get_players_in_social_disgrace DOS veces
    assert mock_get.call_count == 2
    
    # Debe hacer sleep de 0.2s
    mock_sleep.assert_awaited_once_with(0.2)
    
    # Debe hacer commit DOS veces (inicial + retry)
    assert mock_db.commit.call_count == 2
    
    # Debe emitir con la lista FINAL (después del retry)
    mock_ws_service.notificar_social_disgrace_update.assert_awaited_once_with(
        room_id=10,
        game_id=1,
        players_in_disgrace=disgrace_list_final,
        change_info=change_info
    )


@pytest.mark.asyncio
async def test_notify_social_disgrace_change_no_retry_on_exit():
    """Test: NO hace retry cuando action es 'exited'"""
    mock_room = MagicMock(spec=models.Room)
    mock_room.id = 10
    
    mock_db = MagicMock()
    mock_db.close = MagicMock()
    mock_db.is_active = True
    
    change_info = {
        "action": "exited",  # Salida
        "player_id": 5,
        "player_name": "Ana",
        "game_id": 1
    }
    
    mock_ws_service = MagicMock()
    mock_ws_service.notificar_social_disgrace_update = AsyncMock()
    
    with patch('app.db.database.SessionLocal', return_value=mock_db), \
         patch.object(crud, 'get_room_by_game_id', return_value=mock_room), \
         patch.object(social_disgrace_service, 'get_players_in_social_disgrace', return_value=[]) as mock_get, \
         patch('app.sockets.socket_service.get_websocket_service', return_value=mock_ws_service), \
         patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        
        await social_disgrace_service.notify_social_disgrace_change(
            game_id=1,
            change_info=change_info
        )
    
    # NO debe hacer retry porque action es "exited"
    mock_get.assert_called_once()
    mock_sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_social_disgrace_change_db_not_active():
    """Test: maneja correctamente cuando db.is_active es False"""
    mock_room = MagicMock(spec=models.Room)
    mock_room.id = 10
    
    mock_db = MagicMock()
    mock_db.close = MagicMock()
    mock_db.is_active = False  # DB no activa
    
    mock_ws_service = MagicMock()
    mock_ws_service.notificar_social_disgrace_update = AsyncMock()
    
    with patch('app.db.database.SessionLocal', return_value=mock_db), \
         patch.object(crud, 'get_room_by_game_id', return_value=mock_room), \
         patch.object(social_disgrace_service, 'get_players_in_social_disgrace', return_value=[]), \
         patch('app.sockets.socket_service.get_websocket_service', return_value=mock_ws_service):
        
        await social_disgrace_service.notify_social_disgrace_change(
            game_id=1,
            change_info=None
        )
    
    # NO debe llamar a close porque is_active es False
    mock_db.close.assert_not_called()

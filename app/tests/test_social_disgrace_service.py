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

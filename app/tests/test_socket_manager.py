import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import logging

from app.sockets.socket_manager import (
    WebSocketManager,
    get_ws_manager,
    init_ws_manager,
)

@pytest.fixture
def mock_sio():
    sio = MagicMock()
    sio.enter_room = AsyncMock()
    sio.leave_room = AsyncMock()
    sio.emit = AsyncMock()
    return sio

@pytest.fixture
def mock_db_factory():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    db.close = MagicMock()
    return lambda: db


# ---------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------

def test_get_room_name(mock_sio, mock_db_factory):
    manager = WebSocketManager(mock_sio, mock_db_factory)
    assert manager.get_room_name(10) == "game_10"


def test_get_sids_and_user_session(mock_sio, mock_db_factory):
    mgr = WebSocketManager(mock_sio, mock_db_factory)
    mgr.user_sessions = {
        "sid1": {"room_id": 1, "user_id": 5},
        "sid2": {"room_id": 2, "user_id": 8},
    }
    assert mgr.get_sids_in_game(1) == ["sid1"]
    assert mgr.get_user_session("sid2") == {"room_id": 2, "user_id": 8}


def test_init_and_get_ws_manager(mock_sio, mock_db_factory):
    mgr = init_ws_manager(mock_sio, mock_db_factory)
    assert get_ws_manager() is mgr

    from app.sockets import socket_manager
    socket_manager._ws_manager = None
    with pytest.raises(RuntimeError):
        get_ws_manager()


# ---------------------------------------------------------------------
# join_game_room
# ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_join_game_room_success(mock_sio, mock_db_factory):
    mgr = WebSocketManager(mock_sio, mock_db_factory)

    mgr.get_room_participants = AsyncMock(return_value=[{"id": 1, "name": "P1"}])

    ok = await mgr.join_game_room("sid1", 5, 10)
    assert ok is True
    mock_sio.enter_room.assert_awaited_once()


@pytest.mark.asyncio
async def test_join_game_room_exception(mock_sio, mock_db_factory):
    mgr = WebSocketManager(mock_sio, mock_db_factory)
    mgr.get_room_name = MagicMock(side_effect=Exception("fail"))

    ok = await mgr.join_game_room("sid2", 7, 99)
    assert ok is False
    mock_sio.emit.assert_any_await("error", {"message": "Error uniendose a la partida"}, room="sid2")


# ---------------------------------------------------------------------
# leave_game_room
# ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leave_game_room_success(mock_sio, mock_db_factory):
    mgr = WebSocketManager(mock_sio, mock_db_factory)
    mgr.user_sessions = {
        "sidX": {"user_id": 1, "game_id": 10, "room_id": 10}
    }
    await mgr.leave_game_room("sidX")
    mock_sio.leave_room.assert_awaited_once_with("sidX", "game_10")


@pytest.mark.asyncio
async def test_leave_game_room_sid_not_found(mock_sio, mock_db_factory):
    mgr = WebSocketManager(mock_sio, mock_db_factory)
    await mgr.leave_game_room("unknown_sid")
    mock_sio.leave_room.assert_not_awaited()


@pytest.mark.asyncio
async def test_leave_game_room_exception(mock_sio, mock_db_factory, caplog):
    mgr = WebSocketManager(mock_sio, mock_db_factory)
    mgr.user_sessions = {"sid3": {"user_id": 1, "game_id": 99}}
    mgr.sio.leave_room = AsyncMock(side_effect=Exception("boom"))

    caplog.set_level(logging.ERROR)
    await mgr.leave_game_room("sid3")
    assert "Error leaving room" in caplog.text


# ---------------------------------------------------------------------
# get_room_participants
# ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_room_participants_success(mock_sio):
    mock_db = MagicMock()
    player1 = MagicMock(id=1, name="Ana", avatar_src="a.png", is_host=True, order=1)
    mock_db.query.return_value.filter.return_value.all.return_value = [player1]
    db_factory = lambda: mock_db

    mgr = WebSocketManager(mock_sio, db_factory)
    mgr.user_sessions = {
        "sid1": {"user_id": 1, "room_id": 5, "connected_at": datetime.now().isoformat()}
    }

    result = await mgr.get_room_participants(5)
    assert result[0]["id"] == 1
    assert "connected_at" in result[0]
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_room_participants_empty(mock_sio, mock_db_factory):
    mgr = WebSocketManager(mock_sio, mock_db_factory)
    result = await mgr.get_room_participants(5)
    assert result == []

# ---------------------------------------------------------------------
# emit_to_room / emit_to_sid
# ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_emit_to_room_with_players(mock_sio, mock_db_factory):
    mgr = WebSocketManager(mock_sio, mock_db_factory)
    mgr.user_sessions = {"s1": {"room_id": 5}}
    await mgr.emit_to_room(5, "eventX", {"x": 1})
    mock_sio.emit.assert_awaited_once_with("eventX", {"x": 1}, room="game_5")


@pytest.mark.asyncio
async def test_emit_to_room_empty_warns(mock_sio, mock_db_factory, caplog):
    mgr = WebSocketManager(mock_sio, mock_db_factory)
    caplog.set_level(logging.WARNING)
    await mgr.emit_to_room(9, "event", {})
    assert "vacía" in caplog.text
    mock_sio.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_emit_to_sid(mock_sio, mock_db_factory):
    mgr = WebSocketManager(mock_sio, mock_db_factory)
    await mgr.emit_to_sid("sid123", "private_evt", {"ok": True})
    mock_sio.emit.assert_awaited_once_with("private_evt", {"ok": True}, to="sid123")

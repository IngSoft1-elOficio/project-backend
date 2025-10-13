import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.sockets import socket_events

@pytest.fixture
def mock_sio():
    """Mock AsyncServer with emit/save_session/get_session."""
    sio = MagicMock()
    sio.emit = AsyncMock()
    sio.save_session = AsyncMock()
    sio.get_session = AsyncMock(return_value={"user_id": 1, "room_id": 10})
    return sio

@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager with join/leave room functions."""
    manager = MagicMock()
    manager.join_game_room = AsyncMock(return_value=True)
    manager.leave_game_room = AsyncMock()
    return manager


@pytest.mark.asyncio
async def test_connect_success(mock_sio, mock_ws_manager):
    with patch("app.sockets.socket_events.get_ws_manager", return_value=mock_ws_manager), \
         patch("app.sockets.socket_events.SessionLocal") as mock_db:
        db_instance = MagicMock()
        mock_db.return_value = db_instance
        mock_room = MagicMock()
        db_instance.query.return_value.filter.return_value.first.return_value = mock_room

        socket_events.register_events(mock_sio)
        connect = mock_sio.event.call_args_list[0][0][0]
        environ = {"QUERY_STRING": "user_id=1&room_id=10"}

        result = await connect("sid123", environ)
        assert result is True
        mock_ws_manager.join_game_room.assert_awaited_once_with("sid123", 10, 1)

        args, kwargs = mock_sio.emit.await_args_list[-1]
        assert args[0] == "connected"
        assert kwargs["room"] == "sid123"


@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected", [
    ("", "user_id required"),
    ("user_id=abc", "invalid user_id format"),
    ("user_id=1", "room_id required"),
    ("user_id=1&room_id=xyz", "invalid room_id format")
])
async def test_connect_invalid_queries(mock_sio, query, expected):
    with patch("app.sockets.socket_events.get_ws_manager") as ws_manager, \
         patch("app.sockets.socket_events.SessionLocal") as mock_db:
        ws_manager.return_value = MagicMock()
        socket_events.register_events(mock_sio)
        connect = mock_sio.event.call_args_list[0][0][0]
        environ = {"QUERY_STRING": query}
        result = await connect("sid", environ)
        assert result is False
        mock_sio.emit.assert_awaited()
        assert expected in str(mock_sio.emit.await_args_list[-1][0][1]["message"])


@pytest.mark.asyncio
async def test_connect_room_not_found(mock_sio, mock_ws_manager):
    with patch("app.sockets.socket_events.get_ws_manager", return_value=mock_ws_manager), \
         patch("app.sockets.socket_events.SessionLocal") as mock_db:
        db_instance = MagicMock()
        mock_db.return_value = db_instance
        db_instance.query.return_value.filter.return_value.first.return_value = None

        socket_events.register_events(mock_sio)
        connect = mock_sio.event.call_args_list[0][0][0]
        environ = {"QUERY_STRING": "user_id=1&room_id=10"}
        result = await connect("sid1", environ)
        assert result is False
        mock_sio.emit.assert_any_await("connect_error", {"message": "room not found"}, room="sid1")

# ----------------
# Disconnect Tests
# ----------------

@pytest.mark.asyncio
async def test_disconnect_success(mock_sio, mock_ws_manager):
    with patch("app.sockets.socket_events.get_ws_manager", return_value=mock_ws_manager):
        socket_events.register_events(mock_sio)
        disconnect = mock_sio.event.call_args_list[1][0][0]  
        await disconnect("sid-disconnect")
        mock_sio.emit.assert_any_await(
            "disconnected",
            {"user_id": 1, "message": "Jugador 1 se desconectó"},
            room="game_10"
        )
        mock_ws_manager.leave_game_room.assert_awaited_once_with("sid-disconnect", 10)


@pytest.mark.asyncio
async def test_disconnect_no_session(mock_sio, mock_ws_manager):
    mock_sio.get_session = AsyncMock(return_value=None)
    with patch("app.sockets.socket_events.get_ws_manager", return_value=mock_ws_manager):
        socket_events.register_events(mock_sio)
        disconnect = mock_sio.event.call_args_list[1][0][0]
        await disconnect("sid-empty")
        mock_ws_manager.leave_game_room.assert_not_awaited()


@pytest.mark.asyncio
async def test_disconnect_exception(mock_sio):
    mock_sio.get_session = AsyncMock(side_effect=Exception("fail-session"))
    with patch("app.sockets.socket_events.get_ws_manager") as ws_manager:
        socket_events.register_events(mock_sio)
        disconnect = mock_sio.event.call_args_list[1][0][0]
        await disconnect("sid-error")
        ws_manager.return_value.leave_game_room.assert_not_called()

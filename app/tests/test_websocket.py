# app/tests/test_socketio.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Fixture para crear un cliente mock individual
@pytest.fixture
def make_mock_sio_client():
    def _make():
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.emit = AsyncMock()
        mock_client.receive = AsyncMock(return_value={"event": "connected"})
        return mock_client
    return _make

# Parcheamos AsyncSimpleClient para devolver mocks independientes
@pytest.fixture
def patch_sio_client(make_mock_sio_client):
    with patch("socketio.AsyncSimpleClient", side_effect=lambda: make_mock_sio_client()):
        yield

@pytest.mark.asyncio
async def test_socketio_connect(patch_sio_client):
    import socketio
    sio_client = socketio.AsyncSimpleClient()
    await sio_client.connect("http://localhost:8000", headers={'user_id': '123'})
    event = await sio_client.receive()
    assert event["event"] == "connected"
    await sio_client.disconnect()
    sio_client.connect.assert_called_once()
    sio_client.disconnect.assert_called_once()

@pytest.mark.asyncio
async def test_joining_game(patch_sio_client):
    import socketio
    sio_client = socketio.AsyncSimpleClient()
    await sio_client.connect("http://localhost:8000", headers={'user_id': '123'})
    await sio_client.emit('join_game', {'game_id': 100, 'user_id': 123})
    sio_client.emit.assert_called_with('join_game', {'game_id': 100, 'user_id': 123})
    event = await sio_client.receive()
    assert event["event"] == "connected"
    await sio_client.disconnect()

@pytest.mark.asyncio
async def test_get_participants(patch_sio_client):
    import socketio
    sio_client1 = socketio.AsyncSimpleClient()
    sio_client2 = socketio.AsyncSimpleClient()

    await sio_client1.connect("http://localhost:8000", headers={'user_id': '123'})
    await sio_client2.connect("http://localhost:8000", headers={'user_id': '124'})

    await sio_client1.emit('join_game', {'game_id': 100, 'user_id': 123})
    await sio_client2.emit('join_game', {'game_id': 100, 'user_id': 124})

    sio_client1.emit.assert_any_call('join_game', {'game_id': 100, 'user_id': 123})
    sio_client2.emit.assert_any_call('join_game', {'game_id': 100, 'user_id': 124})

    await sio_client1.emit('get_participants', {'game_id': 100})
    sio_client1.emit.assert_any_call('get_participants', {'game_id': 100})

    await sio_client1.disconnect()
    await sio_client2.disconnect()
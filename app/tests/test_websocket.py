# app/tests/test_socketio.py
import pytest
import socketio
from fastapi.testclient import TestClient
from app.main import socket_app  # important: use socket_app, not app

@pytest.mark.asyncio
async def test_socketio_connect():
    """Probar conexion"""
    sio_client = socketio.AsyncSimpleClient()

    await sio_client.connect(
            "http://localhost:8000",
            headers={'user_id': '123'}
    )
    
    event_connect = await sio_client.receive()

    await sio_client.disconnect()

@pytest.mark.asyncio
async def test_joining_game():
    sio_client = socketio.AsyncSimpleClient()
    await sio_client.connect(
            "http://localhost:8000",
            headers={'user_id': '123'}
    )
    
    # Consumir evento de conexion
    event = await sio_client.receive()
    print(f"Connection event: {event}")
    
    # Emit join_game event
    await sio_client.emit('join_game', {'game_id': 100, 'user_id': 123})
    
    # Wait for responses
    try:
        event1 = await sio_client.receive(timeout=10)
        print(f"joined room event: {event}")

    except Exception as e:
        print(f"Error receiving events: {e}")
    
    await sio_client.disconnect()

@pytest.mark.asyncio
async def test_get_participants():
    sio_client1 = socketio.AsyncSimpleClient()
    sio_client2 = socketio.AsyncSimpleClient()

    await sio_client1.connect(
        "http://localhost:8000",
        headers={'user_id': '123'}
    )

    await sio_client2.connect(
            "http://localhost:8000",
            headers={'user_id': '124'}
    )
    
    # Consumir eventos de conexion
    await sio_client1.receive()
    await sio_client2.receive()
    
    await sio_client1.emit('join_game', {'game_id': 100, 'user_id': 123})
    await sio_client2.emit('join_game', {'game_id': 100, 'user_id': 124})

    # Esperar respuestas
    try:
        event1 = await sio_client1.receive(timeout=10)
        print(f"joined room event: {event1}")
        event2 = await sio_client2.receive(timeout=10)
        print(f"joined room event: {event2}")

    except Exception as e:
        print(f"Error receiving events: {e}")
    
    await sio_client1.emit('get_participants', {'game_id': 100})

    await sio_client1.disconnect()
    await sio_client2.disconnect()

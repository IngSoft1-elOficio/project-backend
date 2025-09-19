# app/tests/test_socketio.py
import pytest
import socketio
from fastapi.testclient import TestClient
from app.main import socket_app  # important: use socket_app, not app


@pytest.mark.asyncio
async def test_socketio_connect():   
    sio_client = socketio.AsyncSimpleClient()

    await sio_client.connect("http://localhost:8000")
    
    event_connect = await sio_client.receive()

    await sio_client.disconnect()

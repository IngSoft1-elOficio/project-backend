# app/tests/test_socketio.py
import pytest
import socketio
from fastapi.testclient import TestClient
from app.main import socket_app  # important: use socket_app, not app


@pytest.mark.asyncio
async def test_socketio_connect():
    client = TestClient(socket_app)

   
    sio_client = socketio.AsyncClient()

    connected_event = {}

    @sio_client.on("connected")
    async def on_connected(data):
        connected_event.update(data)

    await sio_client.connect("http://localhost:8000")

    print(connected_event['message'])

    await sio_client.disconnect()

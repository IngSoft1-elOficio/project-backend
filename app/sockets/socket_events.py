# app/sockets/socket_events.py
async def handle_connect(sid, environ):
    print(f"Client connected: {sid}")

async def handle_disconnect(sid):
    print(f"Client disconnected: {sid}")

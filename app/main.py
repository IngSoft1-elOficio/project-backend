# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
import socketio

# Inicializar FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API with FastAPI and WebSocket support",
    version="1.0.0",
    docs_url="/docs",  # Documentación automática en /docs
    redoc_url="/redoc"
)

# Configurar CORS para desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar SocketIO para WebSocket
sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins=settings.ALLOWED_ORIGINS,
        logger=True, # para debugear
        engineio_logger=True
)

socket_app = socketio.ASGIApp(sio, app)

# importar eventos despues de crear sio
from .sockets.socket_events import register_events
register_events(sio)

# Ruta de prueba
@app.get("/health")
async def health_check():
    return {"status": "healthy", "environment": settings.ENVIRONMENT}

# Incluir rutas de la API
from app.routes import api
app.include_router(api.router)
<<<<<<< HEAD
from app.routes import game
app.include_router(game.router)


# Incluir eventos de WebSocket
from app.sockets import socket_events
sio.on("connect", socket_events.handle_connect)
sio.on("disconnect", socket_events.handle_disconnect)
=======
>>>>>>> develop

from app.routes import game
app.include_router(game.router)


# Incluir eventos de WebSocket
from app.sockets import socket_events
sio.on("connect", socket_events.handle_connect)
sio.on("disconnect", socket_events.handle_disconnect)

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
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS para desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar Socket.IO para WebSocket
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,          # para debugear
    engineio_logger=False
)

# Inicializar manager global
from app.sockets.socket_manager import init_ws_manager
from app.db.database import SessionLocal
init_ws_manager(sio, lambda: SessionLocal())

# Importar y registrar eventos de Socket
from app.sockets.socket_events import register_events
register_events(sio)

# Incluir rutas de la API
from app.routes import get_list
app.include_router(get_list.router)
from app.routes import game
app.include_router(game.router)
from app.routes import start
app.include_router(start.router)
from app.routes import join
app.include_router(join.router)
from app.routes import discard
app.include_router(discard.router)
from app.routes import finish_turn
app.include_router(finish_turn.router)
from app.routes import take_deck
app.include_router(take_deck.router)
from app.routes import play_detective_set
app.include_router(play_detective_set.router)

# Aplicación ASGI con Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# Ruta de prueba para health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "environment": settings.ENVIRONMENT}


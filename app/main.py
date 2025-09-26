# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import discard
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
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar Socket.IO para WebSocket
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.ALLOWED_ORIGINS,
    logger=True,          # para debugear
    engineio_logger=True
)

# Inicializar manager global
from app.sockets.socket_manager import init_ws_manager
init_ws_manager(sio)

# Aplicación ASGI con Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# Importar y registrar eventos de Socket
from app.sockets.socket_events import register_events
register_events(sio)

# Ruta de prueba para health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "environment": settings.ENVIRONMENT}

# Incluir rutas de la API
from app.routes import api
app.include_router(api.router)
app.include_router(discard.router)
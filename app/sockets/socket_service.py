# app/sockets/socket_service.py
from .socket_manager import get_ws_manager
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class WebSocketService:
    """Interface publica para que otros servicios usen WebSocket"""
    def __init__(self):
        self.ws_manager = get_ws_manager()
    
    # Aca impementar los servicios del socket 


_websocket_service = None

def get_websocket_service() -> WebSocketService:
    global _websocket_service
    if _websocket_service is None:
        _websocket_service = WebSocketService()
    return _websocket_service

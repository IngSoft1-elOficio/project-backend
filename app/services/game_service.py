# services/game_service.py
from app.sockets.socket_service import WebSocketService, get_websocket_service
from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

websocket_service = None

def get_websocket_service_instance():
    global websocket_service
    if websocket_service is None:
        websocket_service = get_websocket_service()
    return websocket_service

def get_asesino(game_state: Dict) -> Optional[int]:
    """Devuelvo el id del jugador asesino"""
    for jugador in game_state.get("players", []):
        if jugador.get("role") == "murderer":
            return jugador["id"]
    return None

def get_complice(game_state: Dict) -> Optional[int]:
    """Devuelvo el id del jugador complice"""
    for jugador in game_state.get("players", []):
        if jugador.get("role") =="accomplice":
            return jugador["id"]
    return None

async def procesar_ultima_carta(game_id: int, carta: str, game_state: Dict):
    """Procesa la ultima arta del mazo y detecta el final de la partida"""
    ws_service = get_websocket_service_instance()
    mazo = game_state.get("deck", {}).get("remaining", 0)

    if mazo > 0:
        game_state["deck"]["remaining"] = mazo - 1
        mazo -= 1
    
    if mazo == 0:
        logger.info(f"Fin de mazo alcanzado en game_id {game_id}")
        partida_finalizada = True
        winners: List[Dict] = []

        # Verifico la carta final
        if carta == "The murderer escapes":
            asesino_id = get_asesino(game_state)
            accomp_id = get_complice(game_state)
            if asesino_id:
                winners.append({"role": "murderer", "player_id": asesino_id})
            if accomp_id:
                winners.append({"role": "accomplice", "player_id": accomp_id})
        
        # Cambio estado de la partida
        game_state["game"]["status"] = "finished"

        # Emitir evento de fin de partida
        await websocket_service.emit_to_room(
            game_id,
            "game_finished",
            {
                "winners": winners,
                "reason": "deck_exhausted_murderer_wins"
            }
          )
        
        # Snapshot del final de la partida (no se que tan bien este)
        await websocket_service.emit_to_room(game_id, "game_state", game_state)

        logger.info(f"Partida {game_id} finalizada, winners: {winners}")
    else:
        logger.debug(f"mazo restante: {mazo} cartas, game_id {game_id}")
from app.sockets.socket_service import get_websocket_service
from app.db.models import Room, RoomStatus
from app.db.database import SessionLocal
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

websocket_service = None

def get_websocket_service_instance():
    global websocket_service
    if websocket_service is None:
        websocket_service = get_websocket_service()
    return websocket_service

def get_asesino(game_state: Dict) -> Optional[int]:
    for jugador in game_state.get("players", []):
        if jugador.get("role") == "murderer":
            return jugador["id"]
    return None

def get_complice(game_state: Dict) -> Optional[int]:
    for jugador in game_state.get("players", []):
        if jugador.get("role") == "accomplice":
            return jugador["id"]
    return None


async def finalizar_partida(game_id: int, winners: List[Dict]):
    """Marca la room como FINISH en la base de datos."""
    db = SessionLocal()
    try:
        room = db.query(Room).filter(Room.id_game == game_id).first()
        if not room:
            raise ValueError(f"No se encontró room para game_id={game_id}")

        room.status = RoomStatus.FINISH
        db.add(room)
        db.commit()
        logger.info(f"Persistida partida {game_id} como terminada.")
    finally:
        db.close()


async def procesar_ultima_carta(game_id: int, carta: str, game_state: Dict):
    """Procesa la última carta del mazo y detecta el final de la partida"""
    ws_service = get_websocket_service_instance()
    mazo = game_state.get("deck", {}).get("remaining", 0)

    if mazo > 0:
        game_state["deck"]["remaining"] = mazo - 1
        mazo -= 1

    if mazo == 0:
        logger.info(f"Fin de mazo alcanzado en game_id {game_id}")
        winners: List[Dict] = []

        if carta == "The murderer escapes":
            asesino_id = get_asesino(game_state)
            accomp_id = get_complice(game_state)
            if asesino_id:
                winners.append({"role": "murderer", "player_id": asesino_id})
            if accomp_id:
                winners.append({"role": "accomplice", "player_id": accomp_id})

        game_state["game"]["status"] = "finished"
        game_state["winners"] = winners

        await finalizar_partida(game_id, winners)

        await ws_service.emit_to_room(
            game_id,
            "game_finished",
            {"winners": winners, "reason": "deck_exhausted_murderer_wins"}
        )

        await ws_service.emit_to_room(game_id, "game_state", game_state)

        logger.info(f"Partida {game_id} finalizada, winners: {winners}")
    else:
        logger.debug(f"Mazo restante: {mazo} cartas, game_id {game_id}")
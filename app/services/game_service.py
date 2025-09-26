from app.sockets.socket_service import get_websocket_service
from app.db.models import Room, RoomStatus, CardState, CardsXGame, Player
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


#funciones para descarte

async def descartar_cartas(db, game, user_id, card_ids):
        discarded = (
        db.query(CardsXGame)
        .filter(CardsXGame.id_game == game.id,
                CardsXGame.player_id == user_id,
                CardsXGame.id_card.in_(card_ids),
                CardsXGame.is_in == CardState.HAND)
        .all()
    )
        next_pos = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DISCARD
    ).count()
        for i, card in enumerate(discarded, start=1):
            card.is_in = CardState.DISCARD
            card.position = next_pos + i

        db.commit()
        return discarded


async def robar_cartas_del_mazo(db, game, user_id, cantidad):
    from app.db.models import CardsXGame, CardState
    
    drawn = (
        db.query(CardsXGame)
        .filter(CardsXGame.id_game == game.id,
                CardsXGame.is_in == CardState.DECK)
        .order_by(CardsXGame.position)  
        .limit(cantidad)
        .all()
    )
    for card in drawn:
        card.is_in = CardState.HAND
        card.player_id = user_id
    db.commit()
    return drawn


async def actualizar_turno(db, game):
    players = db.query(Player).filter(Player.id_room == game.rooms[0].id).order_by(Player.order).all()
    ids = [p.id for p in players]

    if game.player_turn_id in ids:
        idx = ids.index(game.player_turn_id)
        next_idx = (idx + 1) % len(ids)
        game.player_turn_id = ids[next_idx]
        db.commit()

    
async def emitir_eventos_ws(game_id, user_id, action, hand, deck, discard):
    ws_service = get_websocket_service_instance()
    
    await ws_service.emit_to_sid(user_id, "action_result", {
        "room_id": game_id,
        "action": action,
        "hand": hand
    })

    await ws_service.emit_to_room(game_id, "deck_updated", deck)
    await ws_service.emit_to_room(game_id, "discard_updated", discard)
    await ws_service.emit_to_room(game_id, "turn_updated", {"current_player_id": user_id})
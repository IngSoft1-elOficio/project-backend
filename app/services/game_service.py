from app.sockets.socket_service import get_websocket_service
from app.db.models import Room, RoomStatus, CardState, CardsXGame, Player
from app.db.models import Room, RoomStatus
from app.db.database import SessionLocal
from typing import Dict, Optional, List
import logging
from app.sockets.socket_manager import get_ws_manager
from sqlalchemy.orm import Session
from datetime import datetime
from ..db import crud

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


def join_game_logic(db: Session, room_id: int, player_data: dict):
    try:
        # Get room by id
        room = crud.get_room_by_id(db, room_id)
        if not room:
            return {"success": False, "error": "room_not_found"}
        
        # Check if room is accepting players
        if room.status != RoomStatus.WAITING:
            return {"success": False, "error": "room_not_waiting"}
        
        # Get current players in the room
        current_players = crud.list_players_by_room(db, room_id)

        print(current_players)
        
        # Check if room is full
        if len(current_players) >= room.player_qty:
            return {"success": False, "error": "room_full"}
        
        # Parse birthdate string to date object
        try:
            birthdate_obj = datetime.strptime(player_data["birthdate"], "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "error": "invalid_birthdate_format"}
        
        # Prepare player data for creation
        new_player_data = {
            "name": player_data["name"],
            "avatar_src": player_data["avatar"],  # 👈 usar el nombre del modelo
            "birthdate": birthdate_obj,
            "id_room": room_id,
            "is_host": False
        }
        
        # Create the new player
        new_player = crud.create_player(db, new_player_data)
        
        # Get updated list of players
        updated_players = crud.list_players_by_room(db, room_id)
        
        return {
            "success": True,
            "room": room,
            "players": updated_players,
            "error": None
        }
    
    except Exception as e:
        print(f"Error in join_game_logic: {e}")
        return {"success": False, "error": "internal_error"}


#funciones para descarte

async def descartar_cartas(db, game, user_id, card_ids):
    discarded = []

    next_pos = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DISCARD
    ).count()

    for i, card_id in enumerate(card_ids, start=1):
        # elimina duplicados
        db.query(CardsXGame).filter(
            CardsXGame.id_game == game.id,
            CardsXGame.id_card == card_id,
            CardsXGame.player_id == user_id,
            CardsXGame.is_in != CardState.HAND
        ).delete(synchronize_session=False)

        # descartar la carta
        card = (
            db.query(CardsXGame)
            .filter(
                CardsXGame.id_game == game.id,
                CardsXGame.player_id == user_id,
                CardsXGame.id_card == card_id,
                CardsXGame.is_in == CardState.HAND
            )
            .first()
        )
        if card:
            card.is_in = CardState.DISCARD
            card.position = next_pos + i
            discarded.append(card)

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
        # resetear dueño
        card.player_id = user_id
        card.is_in = CardState.HAND

    db.commit()
    return drawn


async def actualizar_turno(db, game):
    room = db.query(Room).filter(Room.id_game == game.id).first()
    players = (
        db.query(Player)
        .filter(Player.id_room == room.id)
        .order_by(Player.order)
        .all()
    )
    ids = [p.id for p in players]

    if game.player_turn_id in ids:
        idx = ids.index(game.player_turn_id)
        next_idx = (idx + 1) % len(ids)
        game.player_turn_id = ids[next_idx]
        db.commit()

async def emitir_eventos_ws(game, user_id, action, hand, deck, discard):
    ws = get_ws_manager()

    payload_action = {
        "room_id": game.id,
        "action": action,
        "hand": hand
    }
    
    await ws.emit_to_room(game.id, "action_result", payload_action)
    await ws.emit_to_room(game.id, "deck_updated", deck)
    await ws.emit_to_room(game.id, "discard_updated", discard)
    await ws.emit_to_room(game.id, "turn_updated", {"current_player_id": user_id})


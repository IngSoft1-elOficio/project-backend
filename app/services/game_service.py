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

async def procesar_ultima_carta(game_id: int, room_id: int, carta: str, game_state: Dict, jugador_que_actuo: int):
    """Procesa la última carta del mazo y detecta el final de la partida"""
    from app.sockets.socket_service import get_websocket_service
    
    deck_remaining = game_state.get("mazos", {}).get("deck", 0)

    if deck_remaining == 0:
        logger.info(f"Fin de mazo alcanzado en game_id {game_id}")
        winners: List[Dict] = []

        if carta == "Murder Escapes":
            # Find murderer and accomplice from secretos
            for player_id, secrets in game_state.get("secretos", {}).items():
                for secret in secrets:
                    if secret["name"] == "Secret Murderer":
                        winners.append({"role": "murderer", "player_id": player_id})
                    elif secret["name"] == "Secret Accomplice":
                        winners.append({"role": "accomplice", "player_id": player_id})

        # Update game state to finished
        game_state["status"] = "FINISH"
        
        # Mark room as finished in database
        await finalizar_partida(game_id, winners)

        # Add winners info to game_state
        game_state["winners"] = winners
        game_state["game_finished"] = True
        game_state["finish_reason"] = "deck_exhausted_murderer_wins"

        # Use notificar_estado_partida for consistency
        ws_service = get_websocket_service()
        await ws_service.notificar_estado_partida(
            room_id=room_id,
            jugador_que_actuo=jugador_que_actuo,
            game_state=game_state,
            partida_finalizada=True,
            ganador_id=winners[0]["player_id"] if winners else None  # Primary winner (murderer)
        )
        
        logger.info(f"Partida {game_id} finalizada, winners: {winners}")


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

        # Calculate next order for players
        next_order = len(current_players) + 1
        
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
            "avatar_src": player_data["avatar"],  
            "birthdate": birthdate_obj,
            "id_room": room_id,
            "is_host": False,
            "order": next_order
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

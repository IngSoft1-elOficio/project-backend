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
async def procesar_ultima_carta(game_id: int, room_id: int, game_state: Dict):
    """Procesa la última carta del mazo y detecta el final de la partida"""
    from app.sockets.socket_service import get_websocket_service
    
    # Check deck count from build_complete_game_state structure
    deck_count = game_state.get("mazos", {}).get("deck", {}).get("count", 0)
    
    if deck_count == 1:
        logger.info(f"Fin de mazo alcanzado en game_id {game_id}")
        winners: List[Dict] = []
        
        # Find murderer and accomplice from estados_privados
        estados_privados = game_state.get("estados_privados", {})
        jugadores_info = game_state.get("jugadores", [])

        jugadores_map = {j["player_id"]: j for j in jugadores_info}
        logger.info(f"🔍 Estados privados disponibles: {list(estados_privados.keys())}")
        
        for player_id, estado_privado in estados_privados.items():
            secretos = estado_privado.get("secretos", [])
            player_info = jugadores_map.get(player_id, {})
            logger.info(f"🔍 Player {player_id} ({player_info.get('name', 'Unknown')}): {len(secretos)} secretos")
            
            for secret in secretos:
                secret_name = secret.get("name", "")
                logger.info(f"  - Secret: {secret_name}")
                if secret_name == "You are the Murderer!!":
                    winners.append({
                        "role": "murderer",
                        "player_id": player_id,
                        "name": player_info.get("name", "Unknown"),
                        "avatar_src": player_info.get("avatar_src", "")
                    })
                    logger.info(f"🔪 Asesino encontrado: {player_info.get('name')} (ID: {player_id})")
                elif secret_name == "You are the Accomplice!":
                    winners.append({
                        "role": "accomplice",
                        "player_id": player_id,
                        "name": player_info.get("name", "Unknown"),
                        "avatar_src": player_info.get("avatar_src", "")
                    })
                    logger.info(f"🤝 Cómplice encontrado: {player_info.get('name')} (ID: {player_id})")

        if not winners:
            logger.error(f"⚠️ No se encontraron ganadores!")
            logger.error(f"Estados privados: {estados_privados}")
        else:
            logger.info(f"✅ Ganadores identificados: {winners}")
        
        # Mark room as finished in database
        await finalizar_partida(game_id, winners)
        
        # Notify game ended
        ws_service = get_websocket_service()
        await ws_service.notificar_fin_partida(
            room_id=room_id,
            winners=winners,
            reason="deck_empty"
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
        if len(current_players) >= room.players_max:
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

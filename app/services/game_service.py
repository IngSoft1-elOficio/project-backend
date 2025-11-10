from app.sockets.socket_service import get_websocket_service
from app.db.models import Room, RoomStatus, CardState, CardsXGame, Player, Card
from app.db.models import Room, RoomStatus
from app.db.database import SessionLocal
from typing import Dict, Optional, List
import logging
from app.sockets.socket_manager import get_ws_manager
from sqlalchemy.orm import Session
from datetime import datetime
from ..db import crud
from ..services.social_disgrace_service import get_players_in_social_disgrace
from ..db import models

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
    """Procesa la última carta del draft y detecta el final de la partida"""
    from app.sockets.socket_service import get_websocket_service

    # Check draft count from build_complete_game_state structure
    draft_count = game_state.get("mazos", {}).get("deck", {}).get("draft", [])

    if not draft_count:
        logger.info(f"Fin de draft alcanzado en game_id {game_id}")
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
            print(f"\n✅ Ganadores identificados: {winners}")
        
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

async def win_for_reveal(
    db: Session,
    game_id: int,
    room_id: int,
    revealed_card: CardsXGame
) -> bool:
    """
    Verifica si la carta revelada es el asesino, termina la partida si lo es.
    Args:
        db: Sesion de base de datos
        game_id: ID del juego
        room_id: ID de la sala
        revealed_card: Carta que fue revelada
    Returns:
        True si la partida termino, false si continua.
    """
    #Obtener info de la carta revelada
    card = db.query(Card).filter(Card.id == revealed_card.id_card).first()
    
    if not card:
        logger.warning(f"Carta {revealed_card.id_card} no encontrada en la BD")
        return False
    
    #Verificar si la carta es la del asesino
    if card.name != "You are the Murderer!!":
        return False
    
    #Obtener el jugador que tenia el secreto del asesino
    murderer_player_id = revealed_card.player_id

    #Obtener el complice (si existe)
    accomplice_player_id = await _get_accomplice(db, game_id)
    
    #Obtener la room
    room = db.query(Room).filter(Room.id_game == game_id).first()
    if not room:
        logger.error(f"Room no encontrada {game_id}")
        return False
    
    # Obtener todos los jugadores de la room
    all_players = db.query(Player).filter(Player.id_room == room.id).all()
    
    #Construir lista de perdedores (asesino y complice)
    losers_ids = [murderer_player_id]
    if accomplice_player_id:
        losers_ids.append(accomplice_player_id)
    
    #Construir lista de ganadores (todos los jugadores - complice y asesino)
    winners = []
    for player in all_players:
        if player.id not in losers_ids:
            #Si no es complice o asesino entonces es detective
            winners.append({
                "role": "detective",
                "player_id": player.id,
                "name": player.name,
                "avatar_src": player.avatar_src
            })
    
    if not winners:
        logger.warning("Error, ganadores no encontrados")
    
    #Terminar el juego
    await _end_game_with_winners(
        db=db,
        game_id=game_id,
        room_id=room_id,
        winners=winners,
        reason="murderer_caught"
    )
    
    return True


async def _get_accomplice(db: Session, game_id: int) -> Optional[int]:
    """
    Obtiene el ID del complice (si hay).
    Returns:
        player_id del complice o None
    """
    accomplice_secret = db.query(CardsXGame).join(Card).filter(
        CardsXGame.id_game == game_id,
        Card.name == "You are the Accomplice!",
        CardsXGame.is_in == CardState.SECRET_SET
    ).first()
    
    if accomplice_secret:
        return accomplice_secret.player_id
    
    return None


async def _end_game_with_winners(
    db: Session,
    game_id: int,
    room_id: int,
    winners: List[Dict],
    reason: str
):
    """
    Termina el juego, actualiza el estado de la sala y notifica por websocket.
    Args:
        db: Sesion de base de datos
        game_id: ID del juego
        room_id: ID de la sala
        winners: Lista de ganadores
        reason: Motivo del fin del juego
    """
    #Obtener room
    room = db.query(Room).filter(Room.id == room_id).first()
    
    if not room:
        logger.error(f"Room {room_id} no encontrada")
        return
    
    #Cambiar estado de la sala a FINISH
    room.status = RoomStatus.FINISH
    db.add(room)
    db.commit()
    
    #Emitir evento game_ended por websocket
    ws_service = get_websocket_service()
    await ws_service.notificar_fin_partida(
        room_id=room_id,
        winners=winners,
        reason=reason
    )

async def win_for_total_disgrace(db: Session, game_id: int) -> bool:
    """
    Verifica si el juego termina porque todos los detectives
    están en desgracia social.
    
    Returns:
        True si el juego terminó, False si no.
    """
    logger.debug(f"Checking 'TOTAL_DISGRACE' win condition for game {game_id}...")
    fresh_db = SessionLocal()
    
    try:
        logger.debug(f"Checking 'TOTAL_DISGRACE' win condition for game {game_id}...")
        
        room = fresh_db.query(models.Room).filter(models.Room.id_game == game_id).first() # <-- USA fresh_db
        if not room:
            logger.error(f"Cannot check win condition: Room not found for game {game_id}")
            return False

        # Encontrar al asesino y complice
        villain_ids = set()
        
        murderer_secret = fresh_db.query(models.CardsXGame).join(models.Card).filter(
            models.CardsXGame.id_game == game_id,
            models.Card.name == "You are the Murderer!!",
            models.CardsXGame.is_in == models.CardState.SECRET_SET
        ).first()
        
        if not murderer_secret or not murderer_secret.player_id:
            logger.error(f"Cannot check win condition: Murderer not found for game {game_id}")
            return False 
        
        villain_ids.add(murderer_secret.player_id)
        
        accomplice_id = await _get_accomplice(fresh_db, game_id)
        if accomplice_id:
            villain_ids.add(accomplice_id)

        logger.debug(f"Villain IDs for game {game_id}: {villain_ids}")

        # Encontrar a todos los jugadores ---
        all_players = fresh_db.query(models.Player).filter(models.Player.id_room == room.id).all()
        if not all_players:
            logger.error(f"Cannot check win condition: No players found for game {game_id}")
            return False
            
        # Encontrar jugadores en desgracia ---
        disgraced_players = get_players_in_social_disgrace(fresh_db, game_id)
        disgraced_player_ids = {p['player_id'] for p in disgraced_players}
        
        logger.warning(f"DEBUG (win_for_total_disgrace): Jugadores en desgracia (leído por sesión fresca): {disgraced_player_ids}")

        # Verificacion Logica
        all_good_players_in_disgrace = True
        for player in all_players:
            if player.id in villain_ids:
                continue 
            
            if player.id not in disgraced_player_ids:
                all_good_players_in_disgrace = False 
                break
        
        # Si la condicion se cumple, terminar el juego
        if all_good_players_in_disgrace:
            logger.info(f"¡VICTORIA POR DESGRACIA TOTAL en game {game_id}! Los malos ganan.")
            
            winner_players = [p for p in all_players if p.id in villain_ids]
            winner_list = [
                {"player_id": p.id, "name": p.name} for p in winner_players
            ]
            
            # _end_game_with_winners también crea su propia sesion, pero por si acaso,
            # le pasamos la sesion fresca que sabemos que funciona.
            await _end_game_with_winners( 
                db=fresh_db,
                game_id=game_id,
                room_id=room.id,
                winners=winner_list,
                reason="TOTAL_DISGRACE" 
            )
            return True # El juego termino

        logger.debug("Win condition 'TOTAL_DISGRACE' not met.")
        return False # El juego no termino

    except Exception as e:
        logger.error(f"Error en win_for_total_disgrace: {e}", exc_info=True)
        return False # Asegurarse de retornar False en caso de error
    finally:
        fresh_db.close() #Cierra la sesion fresca.

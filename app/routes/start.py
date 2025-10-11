from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.crud import create_game
from app.db.database import SessionLocal
from app.db.models import Player, Room, Card, CardsXGame, CardState, CardType, RoomStatus
from app.schemas.start import StartRequest
from app.sockets.socket_service import get_websocket_service
from datetime import date, datetime
import typing
import logging
import random

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game/{room_id}", tags=["Games"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/start", status_code=201)
async def start_game(room_id: int, userid: StartRequest, db: Session = Depends(get_db)):
    try:
            
        # Buscar sala
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Sala no encontrada")
        
        # Validar estado de la sala
        if room.status != RoomStatus.WAITING:
            raise HTTPException(status_code=409, detail=f"La sala no está en estado WAITING (actual: {room.status})")

        # Validar jugadores suficientes
        players = db.query(Player).filter(Player.id_room == room.id).all()
        
        if len(players) < room.players_min:
            logger.error(f"Not enough players: {len(players)}/{room.players_min}")
            raise HTTPException(status_code=409, detail=f"No hay suficientes jugadores ({len(players)}/{room.players_min}")

        # Validar host
        isHost = db.query(Player).filter(
            Player.id == userid.user_id,
            Player.is_host == True,
            Player.id_room == room.id
        ).first()
        
        if not isHost:
            raise HTTPException(status_code=403, detail="Solo el host puede iniciar la partida")
        
        # CREAR el juego nuevo
        game = create_game(db, game_data={"player_turn_id": None})

        # Asignar el game a la room
        room.id_game = game.id
        room.status = RoomStatus.INGAME
        db.add(room)
        db.commit()
        db.refresh(room)

        # Ordenar jugadores por cercania de cumpleaños
        ref = date(1890, 9, 15)

        def day_of_year(d: date) -> int:
            return d.timetuple().tm_yday

        ref_day = day_of_year(ref)

        def day_diff(d: date) -> int:
            dy = day_of_year(d)
            diff = abs(dy - ref_day)
            return min(diff, 365 - diff)

        players_sorted = sorted(players, key=lambda p: day_diff(p.birthdate))

        for i, p in enumerate(players_sorted, start=1):
            p.order = i
            db.add(p)
        db.commit()

        # Asignar turno inicial al primer jugador
        first_player = players_sorted[0]
        game.player_turn_id = first_player.id
        db.add(game)
        db.commit()
        db.refresh(game)

        # Repartir cartas
        exclude_special = ['Card Back', 'Murder Escapes', 'Secret Front']

        def pick_cards(card_types: typing.List[CardType], count: int, exclude_names: typing.List[str] = None) -> typing.List[Card]:
            cards = db.query(Card).filter(
                Card.type.in_(card_types),
                ~Card.name.in_(exclude_names or [])
            ).all()
            card_pool = []
            for c in cards:
                card_pool.extend([c] * c.qty)
            random.shuffle(card_pool)
            picked = card_pool[:count]
            return picked

        manos = {}
        secretos = {}

        # Asignar secretos especiales segun cantidad de jugadores
        num_players = len(players_sorted)
        secret_murderer = db.query(Card).filter(Card.name == "You are the Murderer!!").first()
        secret_accomplice = None
        if num_players > 4:
            secret_accomplice = db.query(Card).filter(Card.name == "You are the Accomplice!").first()

        # Seleccionar jugadores al azar para los secretos especiales
        player_indices = list(range(num_players))
        random.shuffle(player_indices)
        
        murderer_player_index = player_indices[0]
        accomplice_player_index = player_indices[1] if num_players > 4 else None

        # Repartir cartas a cada jugador
        for i, p in enumerate(players_sorted):
            game_cards = pick_cards([CardType.EVENT, CardType.DEVIUOS, CardType.DETECTIVE], 5, exclude_special)
            instant_cards = pick_cards([CardType.INSTANT], 1, exclude_special)

            player_secrets: typing.List[Card] = []

            if i == murderer_player_index and secret_murderer:
                player_secrets.append(secret_murderer)
            
            if i == accomplice_player_index and secret_accomplice and num_players > 4:
                player_secrets.append(secret_accomplice)
            
            remaining_secrets_needed = 3 - len(player_secrets)
            if remaining_secrets_needed > 0:
                exclude_special.extend(["You are the Murderer!!", "You are the Accomplice!"])
                normal_secrets = pick_cards([CardType.SECRET], remaining_secrets_needed, exclude_special)
                player_secrets.extend(normal_secrets)

            # Guardar manos y secretos
            manos[p.id] = [{"id": c.id, "name": c.name, "type": c.type} for c in game_cards + instant_cards]
            secretos[p.id] = [{"id": c.id, "name": c.name, "type": c.type} for c in player_secrets]

            # Persistir en DB
            for pos, c in enumerate(game_cards + instant_cards, start=1):
                db.add(CardsXGame(
                    id_game=game.id,
                    id_card=c.id,
                    is_in=CardState.HAND,
                    position=pos,
                    player_id=p.id
                ))
            for pos, c in enumerate(player_secrets, start=1):
                db.add(CardsXGame(
                    id_game=game.id,
                    id_card=c.id,
                    is_in=CardState.SECRET_SET,
                    position=pos,
                    player_id=p.id
                ))

        db.commit()

        # Cartas restantes al deck incluyendo todas sus copias
        remaining_cards = db.query(Card).filter(
            Card.type != CardType.SECRET,
            Card.name != "Card Back",
            Card.name != "Murder Escapes"
        ).all()

        deck_pool = []
        for c in remaining_cards:
            deck_pool.extend([c] * c.qty)

        # Eliminar de deck_pool las cartas que ya estan en mano
        for mano in manos.values():
            for carta in mano:
                for idx, c in enumerate(deck_pool):
                    if c.id == carta['id']:
                        deck_pool.pop(idx)
                        break

        random.shuffle(deck_pool)

        # Agregar "Murder Escapes" como ultima carta del mazo
        murder_escapes = db.query(Card).filter(Card.name == "Murder Escapes").first()
        if murder_escapes:
            deck_pool.append(murder_escapes)

        for pos, c in enumerate(deck_pool, start=1):
            db.add(CardsXGame(
                id_game=game.id,
                id_card=c.id,
                is_in=CardState.DECK,
                position=pos
            ))
        db.commit()

        # Payload respuesta
        payload = {
            "game": {
                "id": game.id,
                "name": room.name,
                "players_min": room.players_min,
                "players_max": room.players_max,
                "status": room.status.value,
                "host_id": isHost.id,
            },
            "turn": {
                "current_player_id": game.player_turn_id,
                "order": [p.id for p in players_sorted],
                "can_act": True,
            }
        }

        # Build game_state
        game_state = {
            "room_id": room_id,
            "game_id": game.id,
            "status": "INGAME",
            "turno_actual": game.player_turn_id,
            "jugadores": [
                {"id": p.id, "name": p.name, "is_host": p.is_host, "order": p.order}
                for p in players_sorted
            ],
            "mazos": {
                "deck": len(deck_pool),
                "discard": {
                    "top": db.query(CardsXGame).filter(
                        CardsXGame.id_game == game.id,
                        CardsXGame.is_in == CardState.DISCARD
                    ).order_by(CardsXGame.position.asc()).first(),
                    "count": 0
                }
            },
            "manos": {p.id: manos[p.id] for p in players_sorted},
            "secretos": {p.id: secretos[p.id] for p in players_sorted},
            "timestamp": datetime.now().isoformat()
        }

        # Notificar via WebSocket
        ws_service = get_websocket_service()
        try:
            await ws_service.notificar_estado_partida(room_id=room_id, game_state=game_state)
        except Exception as e:
            logger.error(f"Failed to notify WebSocket for room {room_id}: {e}")
        
        return payload

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno al iniciar la partida: {str(e)}")
    
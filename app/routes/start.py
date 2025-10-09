from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
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
        
        if len(players) < room.player_qty:
            logger.error(f"Not enough players: {len(players)}/{room.player_qty}")
            raise HTTPException(status_code=409, detail=f"No hay suficientes jugadores ({len(players)}/{room.player_qty})")

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

        # Ordenar jugadores por cercanía de cumpleaños
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
        used_ids: typing.Set[int] = set()

        def pick_cards(card_types: typing.List[CardType], count: int, exclude_names: typing.List[str] = None) -> typing.List[Card]:
            q = db.query(Card).filter( 
                Card.type.in_(card_types), 
                ~Card.id.in_(list(used_ids)),
                ~Card.name.in_(["Card Back", "Murder Escapes", "Secret Front"] + (exclude_names or []))
            ).order_by(func.random()).limit(count)
            picked = q.all()
            for c in picked:
                used_ids.add(c.id)
            return picked

        manos = {}
        secretos = {}

        # Asignar secretos especiales segun cantidad de jugadores
        num_players = len(players_sorted)
        secret_murderer = db.query(Card).filter(Card.name == "Secret Murderer").first()
        used_ids.add(secret_murderer.id)
        secret_accomplice = None
        if num_players > 4:
            secret_accomplice = db.query(Card).filter(Card.name == "Secret Accomplice").first()
            used_ids.add(secret_accomplice.id)

        # Seleccionar jugadores al azar para los secretos especiales
        player_indices = list(range(num_players))
        random.shuffle(player_indices)
        
        murderer_player_index = player_indices[0]
        accomplice_player_index = player_indices[1] if num_players > 4 else None

        # Repartir cartas a cada jugador
        for i, p in enumerate(players_sorted):
            game_cards = pick_cards([CardType.EVENT, CardType.DEVIUOS, CardType.DETECTIVE], 5)
            instant_cards = pick_cards([CardType.INSTANT], 1)

            player_secrets: typing.List[Card] = []

            if i == murderer_player_index and secret_murderer:
                player_secrets.append(secret_murderer)
            
            if i == accomplice_player_index and secret_accomplice and num_players > 4:
                player_secrets.append(secret_accomplice)
            
            remaining_secrets_needed = 3 - len(player_secrets)
            if remaining_secrets_needed > 0:
                exclude_special = ["Secret Murderer", "Secret Accomplice"]
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

        # Cartas restantes al deck
        remaining = db.query(Card).filter(
            ~Card.id.in_(list(used_ids)),
            Card.type != CardType.SECRET,
            Card.name != "Card Back",
            Card.name != "Murder Escapes"
        ).order_by(func.random()).all()

        # Agregar "Murder Escapes" como última carta del mazo
        murder_escapes = db.query(Card).filter(Card.name == "Murder Escapes").first()
        if murder_escapes:
            remaining.append(murder_escapes)

        for pos, c in enumerate(remaining, start=1):
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
                "player_qty": room.player_qty,
                "status": room.status,
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
                "deck": len(remaining),
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
    
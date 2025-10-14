from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.crud import create_game
from app.db.database import SessionLocal
from app.db.models import Player, Room, Card, CardsXGame, CardState, CardType, RoomStatus
from app.schemas.start import StartRequest
from app.sockets.socket_service import get_websocket_service
from datetime import date, datetime
from app.services.game_status_service import build_complete_game_state
import logging
import random
import typing

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
    print(f"🎯 POST /start received: {StartRequest}")

    try:
        # Buscar sala
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Sala no encontrada")

        # Validar estado de la sala
        if room.status != RoomStatus.WAITING:
            raise HTTPException(
                status_code=409,
                detail=f"La sala no está en estado WAITING (actual: {room.status})"
            )

        # Validar jugadores suficientes
        players = db.query(Player).filter(Player.id_room == room.id).all()
        if len(players) < room.players_min or len(players) > room.players_max:
            logger.error(f"Not enough players: {len(players)}/{room.players_min}")
            raise HTTPException(
                status_code=410,
                detail=f"Cantidad incorrecta de jugadores ({len(players)}/ minimo: {room.players_min} - maximo: {room.players_max})"
            )

        # Validar host
        isHost = db.query(Player).filter(
            Player.id == userid.user_id,
            Player.is_host == True,
            Player.id_room == room.id
        ).first()
        if not isHost:
            raise HTTPException(status_code=403, detail="Solo el host puede iniciar la partida")

        # Crear juego
        game = create_game(db, game_data={"player_turn_id": None})
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

        # Turno inicial
        first_player = players_sorted[0]
        game.player_turn_id = first_player.id
        db.add(game)
        db.commit()
        db.refresh(game)

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
            return card_pool[:count]

        manos = {}
        secretos = {}

        # Asignar secretos especiales
        num_players = len(players_sorted)
        secret_murderer = db.query(Card).filter(Card.name == "You are the Murderer!!").first()
        secret_accomplice = db.query(Card).filter(Card.name == "You are the Accomplice!").first() if num_players > 4 else None

        player_indices = list(range(num_players))
        random.shuffle(player_indices)
        murderer_player_index = player_indices[0]
        accomplice_player_index = player_indices[1] if num_players > 4 else None

        # Repartir cartas
        for i, p in enumerate(players_sorted):
            game_cards = pick_cards([CardType.EVENT, CardType.DEVIUOS, CardType.DETECTIVE], 5, exclude_special)
            instant_cards = pick_cards([CardType.INSTANT], 1, exclude_special)

            # Secretos
            player_secrets: typing.List[Card] = []
            if i == murderer_player_index and secret_murderer:
                player_secrets.append(secret_murderer)
            if i == accomplice_player_index and secret_accomplice:
                player_secrets.append(secret_accomplice)

            remaining_secrets_needed = 3 - len(player_secrets)
            if remaining_secrets_needed > 0:
                exclude_special.extend(["You are the Murderer!!", "You are the Accomplice!"])
                player_secrets.extend(pick_cards([CardType.SECRET], remaining_secrets_needed, exclude_special))

            # Persistir en bd
            manos[p.id] = []
            for pos, c in enumerate(game_cards + instant_cards, start=1):
                cxg = CardsXGame(
                    id_game=game.id,
                    id_card=c.id,
                    is_in=CardState.HAND,
                    position=pos,
                    player_id=p.id
                )
                db.add(cxg)
                db.flush()  # genera el id unico sin commit
                manos[p.id].append({
                    "id": cxg.id,
                    "card_id": c.id,
                    "name": c.name,
                    "type": c.type
                })

            secretos[p.id] = []
            for pos, c in enumerate(player_secrets, start=1):
                cxg = CardsXGame(
                    id_game=game.id,
                    id_card=c.id,
                    is_in=CardState.SECRET_SET,
                    position=pos,
                    player_id=p.id
                )
                db.add(cxg)
                db.flush()
                secretos[p.id].append({
                    "id": cxg.id,
                    "card_id": c.id,
                    "name": c.name,
                    "type": c.type
                })

        db.commit()

        remaining_cards = db.query(Card).filter(
            Card.type != CardType.SECRET,
            Card.name != "Card Back",
            Card.name != "Murder Escapes"
        ).all()

        # Draft
        draft_cards = pick_cards([CardType.EVENT, CardType.DEVIUOS, CardType.DETECTIVE], 3, exclude_special)
        draft_cxg = []
        for pos, c in enumerate(draft_cards, start=1):
            cxg = CardsXGame(
                id_game=game.id,
                id_card=c.id,
                is_in=CardState.DRAFT,
                position=pos
            )
            db.add(cxg)
            db.flush()
            draft_cxg.append({
                "id": cxg.id,
                "card_id": c.id,
                "name": c.name,
                "type": c.type
            })

        deck_pool = []
        for c in remaining_cards:
            deck_pool.extend([c] * c.qty)

        # Eliminar cartas que ya estan repartidas
        for mano in manos.values():
            for carta in mano:
                for idx, c in enumerate(deck_pool):
                    if c.id == carta['card_id']:
                        deck_pool.pop(idx)
                        break
        for carta in draft_cards:
            for idx, c in enumerate(deck_pool):
                if c.id == carta.id:
                    deck_pool.pop(idx)
                    break

        random.shuffle(deck_pool)

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

        payload = {
            "game": {
                "id": game.id,
                "name": room.name,
                "players_min": room.players_min,
                "players_max": room.players_max,
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
        game_state = build_complete_game_state(db, game.id)

        # Notificar por WebSocket
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
    
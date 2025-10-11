from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import SessionLocal
from app.schemas.start import StartRequest
from app.db.models import Player, Room, Game, Card, CardsXGame, CardState, CardType, RoomStatus
from app.db.crud import create_game
from app.sockets.socket_service import get_websocket_service
from datetime import date, datetime
import typing
import logging

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
            raise HTTPException(status_code=409, detail=f"No hay suficientes jugadores ({len(players)}/{room.players_min})")

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

        def pick_cards(card_types: typing.List[CardType], count: int) -> typing.List[Card]:
            q = db.query(Card).filter(
                Card.type.in_(card_types),
                ~Card.id.in_(list(used_ids))
            ).order_by(func.random()).limit(count)
            picked = q.all()
            if len(picked) < count:
                more = db.query(Card).filter(
                    ~Card.id.in_(list(used_ids))
                ).order_by(func.random()).limit(count - len(picked)).all()
                picked += more
            for c in picked:
                used_ids.add(c.id)
            return picked

        manos = {}
        secretos = {}

        for p in players_sorted:
            game_cards = pick_cards([CardType.EVENT, CardType.DEVIUOS, CardType.DETECTIVE], 5)
            secret_cards = pick_cards([CardType.SECRET], 3)

            # Evitar que asesino y cómplice estén en la misma mano
            special_names = {"You're the murderer", "You're the accomplice"}
            secret_names = {c.name for c in secret_cards}
            if special_names.issubset(secret_names):
                for c in list(secret_cards):
                    if c.name in special_names:
                        replacement = db.query(Card).filter(
                            Card.type == CardType.SECRET,
                            ~Card.id.in_(list(used_ids)),
                            ~Card.name.in_(list(special_names))
                        ).order_by(func.random()).first()
                        if replacement:
                            used_ids.discard(c.id)
                            try:
                                secret_cards.remove(c)
                            except ValueError:
                                pass
                            secret_cards.append(replacement)
                            used_ids.add(replacement.id)
                            break

            instant_cards = pick_cards([CardType.INSTANT], 1)

            # Guardar manos y secretos
            manos[p.id] = [{"id": c.id, "name": c.name, "type": c.type.value} for c in game_cards + instant_cards]
            secretos[p.id] = [{"id": c.id, "name": c.name, "type": c.type.value} for c in secret_cards]

            # Persistir en DB
            for c in game_cards + instant_cards:
                db.add(CardsXGame(
                    id_game=game.id,
                    id_card=c.id,
                    is_in=CardState.HAND,
                    position=0,
                    player_id=p.id
                ))
            for c in secret_cards:
                db.add(CardsXGame(
                    id_game=game.id,
                    id_card=c.id,
                    is_in=CardState.SECRET_SET,
                    position=0,
                    player_id=p.id
                ))

        db.commit()


        # Cartas restantes al deck
        remaining = db.query(Card).filter(~Card.id.in_(list(used_ids))).order_by(func.random()).all()

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

        # Notify via WebSocket
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
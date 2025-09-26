from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import SessionLocal
from app.schemas.start import StartRequest
from app.db.models import Player, Room, Game, Card, CardsXGame, CardState, CardType, RoomStatus
from app.sockets.socket_manager import get_ws_manager
from datetime import date
import asyncio
import typing

router = APIRouter(prefix="/game/{game_id}", tags=["Games"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/start", status_code=201)
def start_game(game_id: int, userid: StartRequest, db: Session = Depends(get_db)):
    # Validar que la sala esta en estado WAITING
    room = db.query(Room).filter(Room.id == game_id).first()
    if room.status != RoomStatus.WAITING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La sala no está en estado WAITING")

    # Validar que el usuario es el host de la sala
    isHost = db.query(Player).filter(Player.id == userid.user_id, Player.is_host == True, Player.id_room == room.id).first()
    if not isHost:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el host puede iniciar la partida"
        )

    # Validar cantidad de jugadores
    players = db.query(Player).filter(Player.id_room == room.id).all()
    if len(players) < room.player_qty:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No hay suficientes jugadores")

    new_game = Game()
    db.add(new_game)
    db.commit()
    db.refresh(new_game)

    # Cambiar el estado a INGAME
    room.id_game = new_game.id
    room.status = RoomStatus.INGAME
    db.add(room)
    db.commit()

    # Asignar turnos segun fecha de nacimiento
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

    first_player = players_sorted[0]
    new_game.player_turn_id = first_player.id
    db.add(new_game)
    db.commit()

    # Repartir cartas
    used_ids: typing.Set[int] = set()
    def pick_cards(card_types: typing.List[CardType], count: int) -> typing.List[Card]:
        q = db.query(Card).filter(Card.type.in_(card_types), ~Card.id.in_(list(used_ids))).order_by(func.random()).limit(count)
        picked = q.all()
        if len(picked) < count:
            more = db.query(Card).filter(~Card.id.in_(list(used_ids))).order_by(func.random()).limit(count - len(picked)).all()
            picked += more
        for c in picked:
            used_ids.add(c.id)
        return picked

    created_cards = []
    for p in players_sorted:
        game_cards = pick_cards([CardType.EVENT, CardType.DEVIUOS, CardType.DETECTIVE], 5)
        secret_cards = pick_cards([CardType.SECRET], 3)
        # Validar que no se repiten el asesino y el complice
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
        for c in game_cards + instant_cards:
            cx = CardsXGame(id_game=new_game.id, id_card=c.id, is_in=CardState.HAND, position=0, player_id=p.id)
            db.add(cx)
            created_cards.append(cx)
        for c in secret_cards:
            cx = CardsXGame(id_game=new_game.id, id_card=c.id, is_in=CardState.SECRET_SET, position=0, player_id=p.id)
            db.add(cx)
            created_cards.append(cx)

    db.commit()

    remaining = db.query(Card).filter(~Card.id.in_(list(used_ids))).order_by(func.random()).all()
    pos = 1
    for c in remaining:
        cx = CardsXGame(id_game=new_game.id, id_card=c.id, is_in=CardState.DECK, position=pos)
        db.add(cx)
        pos += 1
    db.commit()

    # Notificar via WebSocket
    try:
        ws = get_ws_manager()
        payload = {
            "game": {
                "id": new_game.id,
                "name": room.name,
                "player_qty": room.player_qty,
                "status": room.status,
                "host_id": isHost.id,
            },
            "turn": {
                "current_player_id": new_game.player_turn_id,
                "order": [p.id for p in players_sorted],
                "can_act": True,
            }
        }
        asyncio.create_task(ws.emit_to_room(new_game.id, "game_started", payload))
    except RuntimeError:
        pass

    return payload

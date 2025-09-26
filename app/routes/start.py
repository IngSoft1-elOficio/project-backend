from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.schemas.start import StartRequest
from app.db.models import Player, Room, Game, RoomStatus
from datetime import date

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

    return {""}

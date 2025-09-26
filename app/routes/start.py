from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.schemas.start import StartRequest
from app.db.models import Player, Room, Game, RoomStatus

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

    return {""}
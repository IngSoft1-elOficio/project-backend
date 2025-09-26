from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Room, Player, RoomStatus
from app.schemas.game import GameCreate, GameResponse

router = APIRouter(prefix="/api", tags=["Games"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/game", response_model=GameResponse, status_code=201)
def create_game(newgame: GameCreate, db: Session = Depends(get_db)):
    # Validar nombre unico de la partida
    existing = db.query(Room).filter(Room.name == newgame.room.nombre_partida).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una partida con ese nombre"
        )

    new_room = Room(
        name=newgame.room.nombre_partida,
        player_qty=newgame.room.jugadores,
        status=RoomStatus.WAITING,
    )

    db.add(new_room)
    db.commit()
    db.refresh(new_room)

    new_player = Player(
        is_host=newgame.player.host_id,
        # name=newgame.player.nombre,
        # avatar_src=newgame.player.avatar,
        # birthdate=newgame.player.fechaNacimiento,
    )

    db.add(new_player)
    db.commit()
    db.refresh(new_player)

    return { 
        "id_partida": new_room.id,
        "nombre_partida": new_room.name,
        "jugadores": new_room.player_qty,
        "estado": new_room.status,
        "host_id": new_player.id
    }

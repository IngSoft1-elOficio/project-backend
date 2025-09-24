from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Room, Player, RoomStatus
from app.schemas.game import SessionCreate, GameResponse

router = APIRouter(prefix="/api", tags=["Games"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/newgame", response_model=GameResponse, status_code=201)
def create_game(newgame: SessionCreate, db: Session = Depends(get_db)):
    # Validar nombre unico de la partida
    existing = db.query(Room).filter(Room.name == newgame.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una partida con ese nombre"
        )

    new_room = Room(
        name=newgame.nombre_partida,
        player_qty=newgame.jugadores,
        status=RoomStatus.WAITING,
    )

    db.add(new_room)
    db.commit()
    db.refresh(new_room)

    new_player = Player(
        name=newgame.nombre,
        avatar_src=newgame.avatar,
        birthdate=newgame.fechaNacimiento,
        is_host=newgame.host_id,
    )

    db.add(new_player)
    db.commit()
    db.refresh(new_player)

    return new_room.id

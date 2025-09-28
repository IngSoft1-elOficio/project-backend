from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import crud
from app.db.database import SessionLocal
from app.db import models
from app.schemas.game import GameCreate, GameResponse
from app.services.game_status_service import get_game_status_service
from app.schemas.game_status_schema import GameStateView, ErrorResponse
from typing import Dict, List, Optional
from datetime import datetime, date

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from pydantic import BaseModel
from datetime import date

class PlayerCreateRequest(BaseModel):
    nombre: str
    avatar: str
    fechaNacimiento: str

class RoomCreateRequest(BaseModel):
    nombre_partida: str
    jugadores: int

class GameCreateRequest(BaseModel):
    room: RoomCreateRequest
    player: PlayerCreateRequest

class PlayerResponse(BaseModel):
    id: int
    name: str
    avatar: str
    birthdate: str
    is_host: bool
    model_config = {"from_attributes": True}

class RoomResponse(BaseModel):
    id: int
    name: str
    player_qty: int
    status: str
    host_id: int
    model_config = {"from_attributes": True}

class GameResponse(BaseModel):
    room: RoomResponse
    players: List[PlayerResponse]
    model_config = {"from_attributes": True}

@router.post("/game", response_model=GameResponse, status_code=201)
def create_game(newgame: GameCreateRequest, db: Session = Depends(get_db)):
    print("POST /game received:", newgame)
    
    try:
        # Check if room name already exists
        existing_room = db.query(models.Room).filter(
            models.Room.name == newgame.room.nombre_partida
        ).first()
        
        if existing_room:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una partida con ese nombre"
            )
        
        # 1. Create Game first (parent table)
        game_data = {}
        new_game = crud.create_game(db, game_data)
        
        # 2. Create Room linked to Game
        room_data = {
            "name": newgame.room.nombre_partida,
            "player_qty": newgame.room.jugadores,
            "status": models.RoomStatus.WAITING,
            "id_game": new_game.id
        }
        new_room = crud.create_room(db, room_data)
        
        # 3. Create Host Player linked to Room
        # Convert string date to date object
        try:
            birthdate_obj = datetime.strptime(newgame.player.fechaNacimiento, "%Y-%m-%d").date()
        except ValueError:
            # Try different date formats if needed
            birthdate_obj = datetime.strptime(newgame.player.fechaNacimiento, "%d-%m-%Y").date()
        
        player_data = {
            "name": newgame.player.nombre,
            "avatar_src": newgame.player.avatar,
            "birthdate": birthdate_obj,
            "id_room": new_room.id,
            "is_host": True,
            "order": 1  # Host is first player
        }
        new_player = crud.create_player(db, player_data)
        
        # 6. Return response
        return GameResponse(
            room=RoomResponse(
                id=new_room.id,
                name=new_room.name,
                player_qty=new_room.player_qty,
                status=new_room.status.value,  # Convert enum to string
                host_id=new_player.id
            ),
            players=[
                PlayerResponse(
                    id=new_player.id,
                    name=new_player.name,
                    avatar=new_player.avatar_src,
                    birthdate=new_player.birthdate.strftime("%Y-%m-%d"),
                    is_host=new_player.is_host
                )
            ]
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        print(f"Error creating game: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al crear la partida"
        )

@router.get(
    "/game/{game_id}/status",
    response_model=GameStateView,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Partida o sala no encontrada"},
        403: {"model": ErrorResponse, "description": "Usuario no autorizado"}
    },
    tags=["Games"]
)
async def get_game_status(
    game_id: int,
    user_id: int,  
    db: Session = Depends(get_db)
) -> GameStateView:
    """Obtiene el estado actual de una partida."""
    return get_game_status_service(db, game_id, user_id)
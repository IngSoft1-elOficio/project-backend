from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import crud
from app.db.database import SessionLocal
from app.db import models
from app.schemas.game import GameCreateRequest, GameResponse, RoomResponse, PlayerResponse
from datetime import datetime

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/game", response_model=GameResponse, status_code=201)
def create_game(newgame: GameCreateRequest, db: Session = Depends(get_db)):
    print("POST /game received:", newgame)
    
    try:
        existing_room = db.query(models.Room).filter(
            models.Room.name == newgame.room.nombre_partida
        ).first()
        
        if existing_room:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una partida con ese nombre"
            )
        
        # Create Game first (parent table)
        game_data = {}
        new_game = crud.create_game(db, game_data)
        
        # Create Room linked to Game
        room_data = {
            "name": newgame.room.nombre_partida,
            "players_min": newgame.room.jugadoresMin,
            "players_max": newgame.room.jugadoresMax,
            "status": models.RoomStatus.WAITING,
            "id_game": new_game.id
        }
        new_room = crud.create_room(db, room_data)
        
        # Create Host Player linked to Room
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
        
        return GameResponse(
            room=RoomResponse(
                id=new_room.id,
                name=new_room.name,
                players_min=new_room.players_min,
                players_max=new_room.players_max,
                status=new_room.status, 
                host_id=new_player.id,
                game_id=new_game.id   
            ),
            players=[
                PlayerResponse(
                    id=new_player.id,
                    name=new_player.name,
                    avatar=new_player.avatar_src,
                    birthdate=new_player.birthdate,
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
    
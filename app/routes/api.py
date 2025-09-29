from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from ..db.database import SessionLocal
from ..db.models import Room, Player, RoomStatus
import logging

router = APIRouter(prefix="/api", tags=["API"])
logger = logging.getLogger(__name__)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Response models
class GameItem(BaseModel):
    id: int
    name: str
    player_qty: int
    players_joined: int
    host_id: int | None

    model_config = {"from_attributes": True}

class GameListResponse(BaseModel):
    items: List[GameItem]
    page: int
    limit: int

# Test endpoint
@router.get("/test")
async def test_endpoint():
    return {"message": "Test endpoint is working!"}

# GET /api/game_list
@router.get("/game_list", response_model=GameListResponse)
def get_game_list(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    try:
        # Query rooms in WAITING status
        rooms = (
            db.query(Room)
            .filter(Room.status == RoomStatus.WAITING)
            .order_by(Room.id.desc())
            .all()
        )
        logger.info(f"Retrieved {len(rooms)} rooms in WAITING status")

        available = []
        for room in rooms:
            # Count players in the room
            players = db.query(Player).filter(Player.id_room == room.id).all()
            players_joined = len(players)

            # Find the host
            host = next((p for p in players if p.is_host), None)

            # Include rooms with available slots
            if players_joined < room.player_qty:
                available.append({
                    "id": room.id,
                    "name": room.name,
                    "player_qty": room.player_qty,
                    "players_joined": players_joined,
                    "host_id": host.id if host else None
                })

        # Pagination
        start = (page - 1) * limit
        end = start + limit
        paginated = available[start:end]

        # Commit transaction (optional for read-only, but ensures consistency)
        db.commit()
        logger.debug(f"Returning {len(paginated)} games for page {page}, limit {limit}")

        return GameListResponse(
            items=[GameItem(**r) for r in paginated],
            page=page,
            limit=limit
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error in game_list: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
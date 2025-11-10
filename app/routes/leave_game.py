from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from ..db.database import SessionLocal
from ..db.models import Room, Player, RoomStatus
from ..services.leave_game_service import leave_game_logic
from ..schemas.leave_game import LeaveGameResponse

router = APIRouter()

# Conexion a la DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.delete("/game_join/{room_id}/leave", response_model=LeaveGameResponse)
async def leave_game(
    room_id: int,
    http_user_id: int = Header(..., alias="HTTP_USER_ID"),
    db: Session = Depends(get_db)
):
    """
    Endpoint para cancelar o abandonar una partida en estado WAITING.
    
    - Si es host: cancela la partida -> saca jugadores y elimina sala
    - Si no es host: jugador abandona la sala
    
    Returns:
        200 ok si la accion se completa exitosamente
        404 si room_id no existe
        403 si el jugador no pertenece a esta sala
        409 si la partida ya fue iniciada (status != WAITING)
    """
    print(f"Cancelar o abandonar recibido: room_id={room_id}, user_id={http_user_id}")
    
    try:
        result = await leave_game_logic(db, room_id, http_user_id)
        
        if not result["success"]:
            if result["error"] == "room_not_found":
                raise HTTPException(status_code=404, detail="Sala no encontrada")
            elif result["error"] == "player_not_in_room":
                raise HTTPException(status_code=403, detail="El jugador no pertence a esta sala")
            elif result["error"] == "game_already_started":
                raise HTTPException(status_code=409, detail="La partida ya ha iniciado")
            else:
                raise HTTPException(status_code=400, detail=result["error"])
        
        return LeaveGameResponse(
            status="ok",
            message=result["message"],
            is_host=result["is_host"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al abandonar la partida: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
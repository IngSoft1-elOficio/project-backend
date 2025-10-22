from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.database import SessionLocal
from app.db import crud, models
from app.schemas.event_schema import (
    OneMoreStartRequest, OneMoreStartResponse,
    OneMoreSecondRequest, OneMoreSecondResponse,
    OneMoreThirdRequest, OneMoreThirdResponse
)
from app.sockets.socket_service import get_websocket_service


router = APIRouter(prefix="/api/game", tags=["Events"])

#abro sesion en la bd
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# One-More: Permite elegir un secreto revelado y añadirlo oculto en el set de secretos de cualquier jugador
# STEP 1
@router.post("/{room_id}/event/one-more", response_model = OneMoreStartResponse, status_code = 200)
async def one_more_step_1(
    room_id: int,
    payload: OneMoreStartRequest,
    user_id: int = Header(..., alias = "HTTP_USER_ID"),
    db: Session = Depends(get_db)
):

    #busco sala
    room = crud.get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code = 404, detail = "room_not_found")

    #busco partida
    game = crud.get_game_by_id(db, room.id_game)
    if not game :
        raise HTTPException(status_code = 404 , detail = "game_not_found")

    #validar turno
    if game.player_turn_id != user_id:
        raise HTTPException(status_code = 403, detail = "not_your_turn")

    # Validar que la carta esté en mano del jugador
    event_card = db.query(models.CardsXGame).filter(
        models.CardsXGame.id == payload.card_id,
        models.CardsXGame.player_id == user_id,
        models.CardsXGame.id_game == room.id_game,
        models.CardsXGame.is_in == models.CardState.HAND
    ).first()
    
    if not event_card:
        raise HTTPException(
            status_code=404, 
            detail="Event card not found in your hand"
        )
    
    # Validate card type is EVENT
    if event_card.card.type != models.CardType.EVENT:
        raise HTTPException(
            status_code=400,
            detail="Card is not an event card"
        )
    

    # Crear registro en actions_per_turn
    current_turn = crud.get_current_turn(db, room.id_game)
    action_data = {
        'id_game': room.id_game,
        'turn_id': current_turn.id,
        'player_id': user_id,
        'action_name': models.ActionName.AND_THEN_THERE_WAS_ONE_MORE,
        'action_type': models.ActionType.EVENT_CARD,
        'result': models.ActionResult.SUCCESS,
        'selected_card_id': event_card.id
    }
    
    action = crud.create_action(db, action_data)

    db.commit()
    db.refresh(action)

    #ahora tengo q obtener los secretos revelados y ponerlos en avaliable_secrets
    secrets = db.query(models.CardsXGame).filter(models.CardsXGame.id_game == game.id, 
                                                models.CardsXGame.is_in == models.CardState.SECRET_SET,
                                                models.CardsXGame.hidden == False).all()

    available_secrets = []

    for secret in secrets:
        available_secrets.append({
        "secret_id": secret.id,
        "player_id": secret.player_id,
    })



    #notifico a todos la carta q se esta jugando
    ws_service = get_websocket_service()
    await ws_service.notificar_event_action_started(
        room_id = room_id,
        player_id = user_id,
        event_type = "one_more",
        card_name = "And Then There Was One More",
        step = "selecting_secret"
    )

    return OneMoreStartResponse(
    action_id=action.id,
    available_secrets=available_secrets
)



# One-More: second step seleccionar secreto
@router.post("/{room_id}/event/one-more/select-secret", response_model = OneMoreSecondResponse, status_code = 200)
async def one_more_step_2(
    room_id: int,
    payload: OneMoreSecondRequest,
    user_id: int = Header(..., alias = "HTTP_USER_ID"),
    db: Session = Depends(get_db)
):

    #busco sala
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code = 404, detail = "room_not_found")
    #busco partida
    game = db.query(Game).filter(Game.id == room.id_game).first()
    if not game :
        raise HTTPException(status_code = 404 , detail = "game_not_found")

    #validar turno
    if game.player_turn_id != user_id:
        raise HTTPException(status_code = 403, detail = "not_your_turn")

    #validar si la accion existe y le pertenece al jugador
    action = db.query(ActionsPerTurn).filter(ActionsPerTurn.id == payload.action_id).first()
    if not action:
        raise HTTPException(status_code = 404, detail = "action_not_found")
    
    if action.player_id != user_id:
        raise HTTPException(status_code = 403, detail = "not_your_action")

    #chequear si el secreto existe
    secret = db.query(CardsXGame).filter(CardsXGame.id == payload.selected_secret_id, CardsXGame.id_game == game.id,
                                         CardsXGame.is_in == CardState.SECRET_SET,CardsXGame.hidden == False).first()

    if not secret:
        raise HTTPException(status_code=404, detail="secret_not_found")


    # Crear subacción
    sub_action = ActionsPerTurn(
        id_game = game.id,
        actionName = "and_then_one_more_select_secret",
        player_id = user_id,              
        parent_action_id = payload.action_id,       
        secret_target = payload.selected_secret_id   
    )

    db.add(sub_action)
    db.commit()
    db.refresh(sub_action)

    #guardo los jugadores a los q puedo agregar el secreto
    players = db.query(Player).filter(Player.id_room == room_id).all()
    players_ids = [p.id for p in players]

    ws_service = get_websocket_service()
    await ws_service.notificar_event_step_update(       
    room_id = room_id,        
    player_id= user_id,        
    event_type="one_more",        
    step="secret_selected",        
    message=f"Player {user_id} selected '{secret.card.name}'",        
    data={"secret_id": payload.selected_secret_id, "secret_name": secret.card.name})

    return {
        "allowed_players" : players_ids
    }


# One-More: second step seleccionar secreto
@router.post("/{room_id}/event/one-more/select-player", response_model = OneMoreThirdResponse, status_code = 200)
async def one_more_step_3(
    room_id: int,
    payload: OneMoreThirdRequest,
    user_id: int = Header(..., alias = "HTTP_USER_ID"),
    db: Session = Depends(get_db)
):

    #busco sala
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code = 404, detail = "room_not_found")
    #busco partida
    game = db.query(Game).filter(Game.id == room.id_game).first()
    if not game :
        raise HTTPException(status_code = 404 , detail = "game_not_found")

    #validar turno
    if game.player_turn_id != user_id:
        raise HTTPException(status_code = 403, detail = "not_your_turn")

    #validar si la accion existe y le pertenece al jugador
    action = db.query(ActionsPerTurn).filter(ActionsPerTurn.id == payload.action_id).first()
    if not action:
        raise HTTPException(status_code = 404, detail = "action_not_found")
    
    if action.player_id != user_id:
        raise HTTPException(status_code = 403, detail = "not_your_action")

    #chequear si el secreto existe
    secret = db.query(CardsXGame).filter(CardsXGame.id == action.secret_target, CardsXGame.id_game == game.id).first()

    if not secret:
        raise HTTPException(status_code=404, detail="secret_not_found")

    #muevo el secreto al jugaddor target y lo oculto
    secret.player_id = payload.target_player_id
    secret.hidden = True
    db.commit()


    sub_action = ActionsPerTurn(
    id_game=game.id,
    actionName="and_then_one_more_select_player",
    player_id=user_id,
    parent_action_id=payload.action_id,  # referencia la acción previa
    player_target=payload.target_player_id,
    secret_target=secret.id,
    to_be_hidden=True,
    action_time=datetime.utcnow())

    db.add(sub_action)
    db.commit()
    db.refresh(sub_action)

    # Notificaciones
    ws_service = get_websocket_service()
    await ws_service.notificar_event_step_update(
        room_id=room_id,
        player_id=user_id,
        event_type="one_more",
        step="player_selected",
        message=f"Secret given to Player {payload.target_player_id}",
        data={"target_player_id": payload.target_player_id}
    )

    await ws_service.notificar_event_action_complete(
        room_id=room_id,
        player_id=user_id,
        event_type="one_more"
    )

    await ws_service.notificar_estado_partida()

    # Respuesta final
    return {
        "success": True
    }

"""
Servicio para manejar la lógica de la carta detective Ariadne Oliver.

Ariadne Oliver permite al jugador agregarla a cualquier set de detective
existente de otro jugador. Como efecto, el dueño de ese set debe revelar
uno de sus propios secretos.
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime
import logging

from ..db.models import (
    CardState, ActionType, ActionResult, ActionName, RoomStatus
)
from ..db import crud
from ..schemas.ariadne_oliver_schema import (
    AddOliverToSetRequest,
    AddOliverToSetResponse,
    OliverRevealSecretRequest,
    OliverRevealSecretResponse
)
from ..sockets.socket_service import get_websocket_service
from ..services.game_status_service import build_complete_game_state
from ..services.social_disgrace_service import check_and_notify_social_disgrace
from ..services.game_service import win_for_reveal

logger = logging.getLogger(__name__)


class AriadneOliverService:
    """Servicio para manejar la mecánica de Ariadne Oliver"""
    
    # ID de la carta Ariadne Oliver en la tabla card
    ARIADNE_OLIVER_CARD_ID = 5
    
    # ID del secreto asesino
    MURDERER_SECRET_CARD_ID = 2
    
    def __init__(self, db: Session):
        self.db = db
    
    def add_oliver_to_set(
        self,
        room_id: int,
        request: AddOliverToSetRequest
    ) -> AddOliverToSetResponse:
        """
        Procesa la jugada de Ariadne Oliver agregándola a un set existente.
        
        Validaciones:
        - Room existe y está INGAME
        - Jugador existe y pertenece al juego
        - Es el turno del jugador (game.player_turn_id == player_id)
        - Carta está en la mano del jugador
        - Carta es Ariadne Oliver (cardsxgame.id_card == 5)
        - Target player existe y pertenece al juego
        - Set objetivo existe (hay cartas con ese position y player_id en DETECTIVE_SET)
        
        Acciones:
        - Crea acción padre: ADD_DETECTIVE con action_name=ARIADNE_OLIVER, result=PENDING
        - Mueve carta al set objetivo
        - Notifica WebSocket: detective_oliver_added
        - Actualiza estado público y privado
        
        Args:
            room_id: ID de la sala
            request: AddOliverToSetRequest (player_id, oliver_card_id, target_player_id, target_set_position)
        
        Returns:
            AddOliverToSetResponse (status, action_id, next_action, message)
        
        Raises:
            HTTPException 400/403/404 si validación falla
        """
        # 1. Obtener game_id desde room
        room = crud.get_room_by_id(self.db, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        
        if not room.id_game:
            raise HTTPException(status_code=400, detail="Room has no active game")
        
        game_id = room.id_game
        
        # 2. Validar room status
        if room.status != RoomStatus.INGAME:
            raise HTTPException(
                status_code=400,
                detail="Room is not in game"
            )
        
        # 3. Validar jugador actual
        player = crud.get_player_by_id(self.db, request.player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        if not player.room or player.room.id_game != game_id:
            raise HTTPException(
                status_code=403,
                detail="Player does not belong to this game"
            )
        
        # 4. Validar es el turno del jugador
        game = crud.get_game_by_id(self.db, game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        
        if game.player_turn_id != request.player_id:
            raise HTTPException(
                status_code=403,
                detail="Not your turn"
            )
        
        # 5. Validar carta está en la mano del jugador
        card_xgame = crud.get_card_xgame_by_id(self.db, request.oliver_card_id)
        if not card_xgame:
            raise HTTPException(status_code=404, detail="Card not found")
        
        if card_xgame.player_id != request.player_id or card_xgame.is_in != CardState.HAND:
            raise HTTPException(
                status_code=400,
                detail="Card not in player's hand"
            )
        
        if card_xgame.id_game != game_id:
            raise HTTPException(
                status_code=400,
                detail="Card does not belong to this game"
            )
        
        # 6. Validar que es Ariadne Oliver
        if card_xgame.id_card != self.ARIADNE_OLIVER_CARD_ID:
            raise HTTPException(
                status_code=400,
                detail="Card is not Ariadne Oliver"
            )
        
        # 7. Validar target player existe y pertenece al juego
        target_player = crud.get_player_by_id(self.db, request.target_player_id)
        if not target_player:
            raise HTTPException(status_code=404, detail="Target player not found")
        
        if not target_player.room or target_player.room.id_game != game_id:
            raise HTTPException(
                status_code=403,
                detail="Target player does not belong to this game"
            )
        
        # 8. Validar que el set objetivo existe
        set_cards = crud.get_detective_set_cards_by_position(
            self.db,
            game_id=game_id,
            player_id=request.target_player_id,
            position=request.target_set_position
        )
        
        if not set_cards:
            raise HTTPException(
                status_code=404,
                detail=f"Detective set at position {request.target_set_position} not found for target player"
            )
        
        # 9. Obtener turno actual
        current_turn = crud.get_current_turn(self.db, game_id)
        if not current_turn:
            raise HTTPException(
                status_code=404,
                detail="No active turn found"
            )
        
        # 10. Crear acción padre ADD_DETECTIVE
        parent_action_data = {
            "id_game": game_id,
            "turn_id": current_turn.id,
            "player_id": request.player_id,
            "action_time": datetime.now(),
            "action_name": ActionName.ARIADNE_OLIVER,
            "action_type": ActionType.ADD_DETECTIVE,
            "result": ActionResult.PENDING,
            "selected_card_id": request.oliver_card_id,
            "selected_set_id": request.target_set_position,
            "player_target": request.target_player_id,
            "parent_action_id": None
        }
        
        parent_action = crud.create_action(self.db, parent_action_data)
        self.db.flush()
        
        # 11. Mover carta al set objetivo
        crud.update_single_card_state(
            self.db,
            card_xgame_id=request.oliver_card_id,
            new_state=CardState.DETECTIVE_SET,
            new_position=request.target_set_position,
            player_id=request.target_player_id,
            hidden=False 
        )
        
        self.db.commit()
        self.db.refresh(parent_action)
        
        logger.info(
            f"✅ Ariadne Oliver added to set - "
            f"Player {request.player_id} → Target {request.target_player_id}, "
            f"Set position: {request.target_set_position}, action_id: {parent_action.id}"
        )
        
        # 12. Construir mensaje
        player_name = player.name
        target_name = target_player.name
        message = f"Jugador {player_name} jugó Ariadne Oliver contra {target_name}"
        
        # 13. Notificaciones WebSocket y actualización de estado
        self._notify_oliver_added(
            room_id=room_id,
            game_id=game_id,
            action_id=parent_action.id,
            oliver_player_id=request.player_id,
            oliver_player_name=player_name,
            target_player_id=request.target_player_id,
            target_player_name=target_name,
            set_position=request.target_set_position,
            message=message
        )
        
        return AddOliverToSetResponse(
            status="success",
            action_id=parent_action.id,
            next_action="WAIT_TARGET_REVEAL",
            message=message
        )
    
    def oliver_reveal_secret(
        self,
        room_id: int,
        request: OliverRevealSecretRequest
    ) -> OliverRevealSecretResponse:
        """
        Procesa la revelación de secreto por efecto de Ariadne Oliver.
        
        Validaciones:
        - Acción padre existe y result == PENDING
        - Secreto pertenece al target_player
        - Secreto está en SECRET_SET
        - Player_id del request es el target_player de la acción padre
        
        Acciones:
        - Actualiza CardsXGame.hidden = FALSE
        - Crea acción hija REVEAL_SECRET con action_name=ARIADNE_OLIVER_EFFECT
        - Actualiza acción padre result = SUCCESS
        - Verifica social disgrace
        - Verifica si se reveló el asesino (ganar)
        - Notifica WebSocket: ariadne_oliver_complete
        - Actualiza estado público y privado
        
        Args:
            room_id: ID de la sala
            request: OliverRevealSecretRequest (action_id, secret_id, player_id)
        
        Returns:
            OliverRevealSecretResponse (status, message)
        
        Raises:
            HTTPException 400/404 si validación falla
        """
        # 1. Obtener game_id desde room
        room = crud.get_room_by_id(self.db, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        
        if not room.id_game:
            raise HTTPException(status_code=400, detail="Room has no active game")
        
        game_id = room.id_game
        
        # 2. Validar acción padre existe y está PENDING
        parent_action = crud.get_action_by_id(self.db, request.action_id, game_id)
        if not parent_action:
            raise HTTPException(status_code=404, detail="Action not found")
        
        if parent_action.result != ActionResult.PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Action is not pending (current: {parent_action.result})"
            )
        
        # 3. Validar que el player_id es el target de la acción padre
        if parent_action.player_target != request.player_id:
            raise HTTPException(
                status_code=403,
                detail="You are not the target player of this action"
            )
        
        # 4. Validar que el secreto existe
        secret_card = crud.get_card_xgame_by_id(self.db, request.secret_id)
        if not secret_card:
            raise HTTPException(status_code=404, detail="Secret card not found")
        
        # 5. Validar que el secreto pertenece al target_player
        if secret_card.player_id != request.player_id:
            raise HTTPException(
                status_code=403,
                detail="Secret does not belong to you"
            )
        
        # 6. Validar que está en SECRET_SET
        if secret_card.is_in != CardState.SECRET_SET:
            raise HTTPException(
                status_code=400,
                detail="Card is not a secret"
            )
        
        if secret_card.id_game != game_id:
            raise HTTPException(
                status_code=400,
                detail="Secret does not belong to this game"
            )
        
        # 7. Actualizar visibilidad del secreto
        crud.update_card_visibility(self.db, request.secret_id, hidden=False)
        
        # 8. Crear acción hija REVEAL_SECRET
        child_action_data = {
            "id_game": game_id,
            "turn_id": parent_action.turn_id,
            "player_id": request.player_id,
            "action_time": datetime.now(),
            "action_name": ActionName.ARIADNE_OLIVER_EFFECT,
            "action_type": ActionType.REVEAL_SECRET,
            "result": ActionResult.SUCCESS,
            "secret_target": request.secret_id,
            "parent_action_id": request.action_id
        }
        
        child_action = crud.create_action(self.db, child_action_data)
        self.db.flush()
        
        # 9. Actualizar acción padre a SUCCESS
        crud.update_action_result(self.db, request.action_id, ActionResult.SUCCESS)
        
        self.db.commit()
        
        logger.info(
            f"✅ Ariadne Oliver effect complete - "
            f"Player {request.player_id} revealed secret {request.secret_id}, "
            f"action_id: {child_action.id}"
        )
        
        # 10. Construir mensaje
        player = crud.get_player_by_id(self.db, request.player_id)
        player_name = player.name if player else f"Player {request.player_id}"
        message = f"Jugador {player_name} reveló un secreto! Efecto de Ariadne terminado."
        
        # 11. Verificar social disgrace (sin await, se ejecuta sync)
        import asyncio
        asyncio.create_task(
            check_and_notify_social_disgrace(game_id, request.player_id)
        )
        
        # 12. Verificar si se reveló el asesino (ganar)
        asyncio.create_task(
            win_for_reveal(
                db=self.db,
                game_id=game_id,
                room_id=room_id,
                revealed_card=secret_card
            )
        )
        
        # 13. Notificaciones WebSocket y actualización de estado
        self._notify_oliver_complete(
            room_id=room_id,
            game_id=game_id,
            player_id=request.player_id,
            player_name=player_name,
            message=message
        )
        
        return OliverRevealSecretResponse(
            status="success",
            message=message
        )
    
    # =============================
    # HELPERS - WEBSOCKET
    # =============================
    
    def _notify_oliver_added(
        self,
        room_id: int,
        game_id: int,
        action_id: int,
        oliver_player_id: int,
        oliver_player_name: str,
        target_player_id: int,
        target_player_name: str,
        set_position: int,
        message: str
    ):
        """
        Notifica que Ariadne Oliver fue agregada a un set y actualiza estados.
        
        Emite:
        - WebSocket: detective_oliver_added
        - Estado público: actualiza sets
        - Estado privado: actualiza mano del jugador
        """
        import asyncio
        
        ws_service = get_websocket_service()
        
        # 1. Notificación WebSocket específica
        asyncio.create_task(
            ws_service.notify_detective_oliver_added(
                room_id=room_id,
                action_id=action_id,
                oliver_player_id=oliver_player_id,
                oliver_player_name=oliver_player_name,
                target_player_id=target_player_id,
                target_player_name=target_player_name,
                set_position=set_position,
                message=message
            )
        )
        
        # 2. Actualizar estado del juego
        game_state = build_complete_game_state(self.db, game_id)
        
        # 3. Notificar estado público (actualiza sets)
        asyncio.create_task(
            ws_service.notificar_estado_publico(
                room_id=room_id,
                game_state=game_state
            )
        )
        
        # 4. Notificar estados privados (actualiza mano del jugador)
        if game_state.get("estados_privados"):
            asyncio.create_task(
                ws_service.notificar_estados_privados(
                    room_id=room_id,
                    estados_privados=game_state["estados_privados"]
                )
            )
        
        logger.info(f"📡 Notified Ariadne Oliver added to room {room_id}")
    
    def _notify_oliver_complete(
        self,
        room_id: int,
        game_id: int,
        player_id: int,
        player_name: str,
        message: str
    ):
        """
        Notifica que el efecto de Ariadne Oliver se completó y actualiza estados.
        
        Emite:
        - WebSocket: ariadne_oliver_complete
        - Estado público: actualiza secretos revelados
        - Estado privado: actualiza secretos del jugador
        """
        import asyncio
        
        ws_service = get_websocket_service()
        
        # 1. Notificación WebSocket específica
        asyncio.create_task(
            ws_service.notify_ariadne_oliver_complete(
                room_id=room_id,
                player_id=player_id,
                player_name=player_name,
                message=message
            )
        )
        
        # 2. Actualizar estado del juego
        game_state = build_complete_game_state(self.db, game_id)
        
        # 3. Notificar estado público (actualiza secretos revelados)
        asyncio.create_task(
            ws_service.notificar_estado_publico(
                room_id=room_id,
                game_state=game_state
            )
        )
        
        # 4. Notificar estados privados (actualiza secretos del jugador)
        if game_state.get("estados_privados"):
            asyncio.create_task(
                ws_service.notificar_estados_privados(
                    room_id=room_id,
                    estados_privados=game_state["estados_privados"]
                )
            )
        
        logger.info(f"📡 Notified Ariadne Oliver complete to room {room_id}")

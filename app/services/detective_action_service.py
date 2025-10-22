# app/services/detective_action_service.py
from sqlalchemy.orm import Session
from typing import Tuple, Optional, List
from fastapi import HTTPException

from ..db.models import (
    Game, Player, CardsXGame, ActionsPerTurn, Card,
    CardState, ActionType, ActionResult
)
from ..db import crud
from ..schemas.detective_action_schema import (
    DetectiveActionRequest, DetectiveActionResponse,
    RevealedSecret, HiddenSecret, TransferredSecret, EffectsSummary
)
from ..schemas.detective_set_schema import SetType, NextAction, NextActionType, NextActionMetadata, SecretInfo


class DetectiveActionService:
    """Servicio para ejecutar acciones de detective pendientes"""
    
    # Mapeo de action_name a SetType para determinar el comportamiento
    ACTION_TO_SET_TYPE = {
        "play_Poirot_set": SetType.POIROT,
        "play_Marple_set": SetType.MARPLE,
        "play_Satterthwaite_set": SetType.SATTERTHWAITE,
        "play_Pyne_set": SetType.PYNE,
        "play_EileenBrent_set": SetType.EILEENBRENT,
        "play_Beresford_set": SetType.BERESFORD,
    }
    
    # Sets donde el activo elige jugador + secreto
    ACTIVE_SELECTS_ALL = [SetType.POIROT, SetType.MARPLE, SetType.PYNE]
    
    # Sets donde el target elige su propio secreto
    TARGET_SELECTS_OWN = [SetType.SATTERTHWAITE, SetType.BERESFORD, SetType.EILEENBRENT]
    
    def __init__(self, db: Session):
        self.db = db
    
    def execute_detective_action(
        self,
        game_id: int,
        request: DetectiveActionRequest
    ) -> DetectiveActionResponse:
        """
        Ejecuta una acción de detective pendiente.
        Soporta flujo de 1 paso (Marple, Poirot, Pyne) y 2 pasos (Satterthwaite, Beresford, Eileen).
        
        Returns:
            DetectiveActionResponse con el resultado de la ejecución
        
        Raises:
            HTTPException con códigos 400, 403, 404, 409
        """
        game = self._get_game(game_id)
        action = self._get_pending_action(request.actionId, game_id)
        set_type = self._get_set_type(action.action_name)
        owner_id = action.player_id
        
        # Detectar si es un detective de 2 pasos
        if set_type in self.TARGET_SELECTS_OWN:
            # Satterthwaite, Beresford, Eileen - Flujo de 2 pasos
            if request.targetPlayerId and not request.secretId:
                # PASO 1: Owner selecciona target
                return self._handle_target_selection(game_id, action, request, set_type, owner_id)
            elif request.secretId and not request.targetPlayerId:
                # PASO 2: Target selecciona secreto
                return self._handle_secret_selection(game_id, action, request, set_type, owner_id)
            else:
                raise HTTPException(
                    status_code=400,
                    detail="For 2-step detectives: provide targetPlayerId in step 1, then secretId in step 2"
                )
        
        # Detectives de 1 paso (Marple, Poirot, Pyne)
        return self._handle_single_step_action(game_id, action, request, set_type, owner_id)
    
    def _handle_single_step_action(
        self,
        game_id: int,
        action: ActionsPerTurn,
        request: DetectiveActionRequest,
        set_type: SetType,
        owner_id: int
    ) -> DetectiveActionResponse:
        """Maneja detectives de 1 paso (Marple, Poirot, Pyne)"""
        self._validate_executor(request.executorId, owner_id, set_type, request.targetPlayerId)
        
        executor = self._get_player(request.executorId, game_id)
        target_player_id = self._validate_inputs(request, set_type, owner_id)
        secret_card = self._get_secret_card(request.secretId, target_player_id, game_id)
        self._validate_secret(secret_card, set_type)
        
        has_wildcard = self._check_action_has_wildcard(action)
        
        effects = self._apply_effect(
            set_type=set_type,
            secret_card=secret_card,
            target_player_id=target_player_id,
            owner_id=owner_id,
            has_wildcard=has_wildcard,
            game_id=game_id,
            action=action,
            executor_id=request.executorId
        )
        
        crud.update_action_result(self.db, action.id, ActionResult.SUCCESS)
        self.db.commit()
        
        return DetectiveActionResponse(
            success=True,
            completed=True,
            nextAction=None,
            effects=effects
        )
    
    def _handle_target_selection(
        self,
        game_id: int,
        action: ActionsPerTurn,
        request: DetectiveActionRequest,
        set_type: SetType,
        owner_id: int
    ) -> DetectiveActionResponse:
        """
        PASO 1: Owner selecciona el target player.
        Guarda el target en ActionsPerTurn y retorna nextAction para que el target elija su secreto.
        """
        # Validar que el executor es el owner
        if request.executorId != owner_id:
            raise HTTPException(
                status_code=403,
                detail="Only the set owner can select the target"
            )
        
        # Validar que targetPlayerId fue provisto
        if not request.targetPlayerId:
            raise HTTPException(
                status_code=400,
                detail="targetPlayerId is required in step 1"
            )
        
        # Validar que el target existe y pertenece al juego
        target_player = self._get_player(request.targetPlayerId, game_id)
        
        # No puede seleccionarse a sí mismo
        if request.targetPlayerId == owner_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot target yourself"
            )
        
        # Guardar el target_player_id en la acción
        # Usamos el campo player_target que ya existe en ActionsPerTurn
        action.player_target = request.targetPlayerId
        self.db.flush()
        
        # Obtener la lista de secretos disponibles del target (para nextAction)
        available_secrets = self._get_player_secrets(game_id, request.targetPlayerId, set_type)
        
        # Crear nextAction para que el target seleccione su secreto
        from app.schemas.detective_set_schema import NextActionType, NextActionMetadata, SecretInfo
        
        has_wildcard = self._check_action_has_wildcard(action)
        
        next_action = NextAction(
            type=NextActionType.WAIT_FOR_OPPONENT,
            allowedPlayers=[request.targetPlayerId],
            metadata=NextActionMetadata(
                hasWildcard=has_wildcard,
                secretsPool=available_secrets
            )
        )
        
        self.db.commit()
        
        return DetectiveActionResponse(
            success=True,
            completed=False,  # Acción NO completada aún
            nextAction=next_action,
            effects=EffectsSummary(revealed=[], hidden=[], transferred=[])
        )
    
    def _handle_secret_selection(
        self,
        game_id: int,
        action: ActionsPerTurn,
        request: DetectiveActionRequest,
        set_type: SetType,
        owner_id: int
    ) -> DetectiveActionResponse:
        """
        PASO 2: Target selecciona su propio secreto.
        Aplica los efectos y completa la acción.
        """
        # Obtener el target_player_id guardado en el paso 1
        if not action.player_target:
            raise HTTPException(
                status_code=400,
                detail="Target player was not selected in step 1"
            )
        
        target_player_id = action.player_target
        
        # Validar que el executor es el target
        if request.executorId != target_player_id:
            raise HTTPException(
                status_code=403,
                detail="Only the target player can select their secret"
            )
        
        # Validar que secretId fue provisto
        if not request.secretId:
            raise HTTPException(
                status_code=400,
                detail="secretId is required in step 2"
            )
        
        # Obtener y validar el secreto
        secret_card = self._get_secret_card(request.secretId, target_player_id, game_id)
        self._validate_secret(secret_card, set_type)
        
        has_wildcard = self._check_action_has_wildcard(action)
        
        # Aplicar el efecto
        effects = self._apply_effect(
            set_type=set_type,
            secret_card=secret_card,
            target_player_id=target_player_id,
            owner_id=owner_id,
            has_wildcard=has_wildcard,
            game_id=game_id,
            action=action,
            executor_id=request.executorId
        )
        
        # Marcar la acción como completada
        crud.update_action_result(self.db, action.id, ActionResult.SUCCESS)
        self.db.commit()
        
        return DetectiveActionResponse(
            success=True,
            completed=True,  # Acción COMPLETADA
            nextAction=None,
            effects=effects
        )
    
    def _get_player_secrets(
        self,
        game_id: int,
        player_id: int,
        set_type: SetType
    ) -> List:
        """Obtiene la lista de secretos disponibles de un jugador para nextAction"""
        from app.schemas.detective_set_schema import SecretInfo
        
        # Obtener secretos del jugador
        query = self.db.query(CardsXGame).filter(
            CardsXGame.id_game == game_id,
            CardsXGame.player_id == player_id,
            CardsXGame.is_in == CardState.SECRET_SET
        )
        
        # Filtrar según el tipo de detective
        if set_type == SetType.PYNE:
            # Pyne solo puede ocultar secretos revelados
            query = query.filter(CardsXGame.hidden == False)
        else:
            # Otros revelan/transfieren secretos ocultos
            query = query.filter(CardsXGame.hidden == True)
        
        secrets = query.order_by(CardsXGame.position).all()
        
        # Convertir a SecretInfo
        secret_list = []
        for secret in secrets:
            card_id = None if secret.hidden else secret.id_card
            secret_list.append(SecretInfo(
                playerId=player_id,
                position=secret.position,
                hidden=secret.hidden,
                cardId=card_id
            ))
        
        return secret_list
    
    def _get_game(self, game_id: int) -> Game:
        """Obtiene el juego o lanza 404"""
        game = crud.get_game_by_id(self.db, game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        return game
    
    def _get_pending_action(self, action_id: int, game_id: int) -> ActionsPerTurn:
        """Obtiene la acción pendiente o lanza error"""
        action = crud.get_action_by_id(self.db, action_id)
        
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        
        if action.id_game != game_id:
            raise HTTPException(status_code=400, detail="Action does not belong to this game")
        
        if action.result != ActionResult.PENDING:
            raise HTTPException(
                status_code=409,
                detail=f"Action is not pending (current status: {action.result.value})"
            )
        
        if action.action_type != ActionType.DETECTIVE_SET:
            raise HTTPException(
                status_code=400,
                detail="Action is not a detective set action"
            )
        
        return action
    
    def _get_set_type(self, action_name: str) -> SetType:
        """Obtiene el SetType desde el action_name"""
        set_type = self.ACTION_TO_SET_TYPE.get(action_name)
        
        if not set_type:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown action name: {action_name}"
            )
        
        return set_type
    
    def _validate_executor(
        self,
        executor_id: int,
        owner_id: int,
        set_type: SetType,
        target_player_id: Optional[int]
    ):
        """Valida que el executor sea el correcto según el tipo de set"""
        if set_type in self.ACTIVE_SELECTS_ALL:
            if executor_id != owner_id:
                raise HTTPException(
                    status_code=403,
                    detail="Only the set owner can execute this action"
                )
        
        elif set_type in self.TARGET_SELECTS_OWN:
            if not target_player_id:
                raise HTTPException(
                    status_code=400,
                    detail="targetPlayerId is required for this set type"
                )
            
            if executor_id != target_player_id:
                raise HTTPException(
                    status_code=403,
                    detail="Only the target player can execute this action"
                )
    
    def _get_player(self, player_id: int, game_id: int) -> Player:
        """Valida que el jugador existe y pertenece al juego"""
        player = crud.get_player_by_id(self.db, player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        if not player.room or player.room.id_game != game_id:
            raise HTTPException(
                status_code=403,
                detail="Player does not belong to this game"
            )
        
        return player
    
    def _validate_inputs(
        self,
        request: DetectiveActionRequest,
        set_type: SetType,
        owner_id: int
    ) -> int:
        """
        Valida que los inputs requeridos estén presentes según el tipo de set.
        
        Returns:
            target_player_id: El ID del jugador cuyo secreto será afectado
        """
        # Todos los sets requieren secretId
        if request.secretId is None:
            raise HTTPException(status_code=400, detail="secretId is required")
        
        if set_type in self.ACTIVE_SELECTS_ALL:
            # Marple, Poirot, Pyne: requieren targetPlayerId
            if request.targetPlayerId is None:
                raise HTTPException(
                    status_code=400,
                    detail="targetPlayerId is required for this set type"
                )
            
            # No puede ser el mismo owner
            if request.targetPlayerId == owner_id:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot target yourself"
                )
            
            return request.targetPlayerId
        
        elif set_type in self.TARGET_SELECTS_OWN:
            return request.executorId
        
        raise HTTPException(status_code=500, detail="Unknown set type")
    
    def _get_secret_card(
        self,
        secret_id: int,
        target_player_id: int,
        game_id: int
    ) -> CardsXGame:
        """Obtiene la carta del secreto y valida que pertenece al target"""
        secret_card = self.db.query(CardsXGame).filter(CardsXGame.id == secret_id).first()
        
        if not secret_card:
            raise HTTPException(status_code=404, detail="Secret card not found")
        
        if secret_card.id_game != game_id:
            raise HTTPException(
                status_code=400,
                detail="Secret card does not belong to this game"
            )
        
        if secret_card.player_id != target_player_id:
            raise HTTPException(
                status_code=400,
                detail="Secret card does not belong to the target player"
            )
        
        if secret_card.is_in != CardState.SECRET_SET:
            raise HTTPException(
                status_code=400,
                detail="Card is not in a secret set"
            )
        
        return secret_card
    
    def _validate_secret(self, secret_card: CardsXGame, set_type: SetType):
        """Valida que el secreto cumple las restricciones del tipo de set"""
        if set_type == SetType.PYNE:
            if secret_card.hidden:
                raise HTTPException(
                    status_code=400,
                    detail="Parker Pyne can only hide revealed secrets"
                )
        else:
            if not secret_card.hidden:
                raise HTTPException(
                    status_code=400,
                    detail="This detective can only reveal hidden secrets"
                )
    
    def _check_action_has_wildcard(self, action: ActionsPerTurn) -> bool:
        """
        Verifica si el set de detective incluía un comodín.
        Busca las cartas del set bajado en DETECTIVE_SET.
        """
        HARLEY_QUIN_CARD_ID = 4
        
        # Obtener las cartas del set de detective recién bajado
        # Asumimos que tienen la position correspondiente al set
        detective_cards = self.db.query(CardsXGame).filter(
            CardsXGame.id_game == action.id_game,
            CardsXGame.player_id == action.player_id,
            CardsXGame.is_in == CardState.DETECTIVE_SET
        ).all()
        
        # Verificar si alguna es Harley Quin
        for card in detective_cards:
            if card.id_card == HARLEY_QUIN_CARD_ID:
                return True
        
        return False
    
    def _apply_effect(
        self,
        set_type: SetType,
        secret_card: CardsXGame,
        target_player_id: int,
        owner_id: int,
        has_wildcard: bool,
        game_id: int,
        action: ActionsPerTurn,
        executor_id: int
    ) -> EffectsSummary:
        """Aplica el efecto correspondiente según el tipo de set"""
        effects = EffectsSummary()
        
        if set_type == SetType.PYNE:
            # Parker Pyne: OCULTA un secreto revelado
            effects.hidden.append(
                self._apply_hide_effect(secret_card, target_player_id, action, executor_id)
            )
        
        elif set_type == SetType.SATTERTHWAITE:
            # Mr. Satterthwaite: REVELA y opcionalmente TRANSFIERE
            revealed = self._apply_reveal_effect(secret_card, target_player_id, action, executor_id)
            effects.revealed.append(revealed)
            
            if has_wildcard:
                # Transferir el secreto revelado face-down al owner
                transferred = self._apply_transfer_effect(
                    secret_card=secret_card,
                    from_player_id=target_player_id,
                    to_player_id=owner_id,
                    game_id=game_id,
                    action=action,
                    executor_id=executor_id
                )
                effects.transferred.append(transferred)
        
        else:
            # Poirot, Marple, Beresford, Eileen: REVELAN
            effects.revealed.append(
                self._apply_reveal_effect(secret_card, target_player_id, action, executor_id)
            )
        
        return effects
    
    def _apply_reveal_effect(
        self,
        secret_card: CardsXGame,
        target_player_id: int,
        action: ActionsPerTurn,
        executor_id: int
    ) -> RevealedSecret:
        """Revela un secreto (hidden=False)"""
        # Obtener info de la carta
        card = crud.get_card_info_by_id(self.db, secret_card.id_card)
        
        # Actualizar el secreto a revelado
        crud.update_card_visibility(self.db, secret_card.id, hidden=False)
        
        # Registrar la acción en ActionsPerTurn
        crud.create_action(self.db, {
            "id_game": action.id_game,
            "turn_id": action.turn_id,
            "player_id": executor_id,  # Quien ejecuta la acción
            "action_name": "reveal_secret",
            "action_type": ActionType.REVEAL_SECRET,
            "result": ActionResult.SUCCESS,
            "parent_action_id": action.id,
            "triggered_by_action_id": action.id,
            "player_source": action.player_id,  # Quien bajó el set
            "player_target": target_player_id,  # Dueño del secreto
            "secret_target": secret_card.id,
            "position_card": secret_card.position,
            "to_be_hidden": 0  # Se está revelando (False = 0)
        })
        
        return RevealedSecret(
            playerId=target_player_id,
            secretId=secret_card.id,
            cardId=card.id,
            cardName=card.name,
            imgSrc=card.img_src,
            position=secret_card.position
        )
    
    def _apply_hide_effect(
        self,
        secret_card: CardsXGame,
        target_player_id: int,
        action: ActionsPerTurn,
        executor_id: int
    ) -> HiddenSecret:
        """Oculta un secreto revelado (hidden=True)"""
        # Actualizar el secreto a oculto
        crud.update_card_visibility(self.db, secret_card.id, hidden=True)
        
        # Registrar la acción en ActionsPerTurn
        crud.create_action(self.db, {
            "id_game": action.id_game,
            "turn_id": action.turn_id,
            "player_id": executor_id,  # Quien ejecuta la acción
            "action_name": "hide_secret",
            "action_type": ActionType.HIDE_SECRET,
            "result": ActionResult.SUCCESS,
            "parent_action_id": action.id,
            "triggered_by_action_id": action.id,
            "player_source": action.player_id,  # Quien bajó el set
            "player_target": target_player_id,  # Dueño del secreto
            "secret_target": secret_card.id,
            "position_card": secret_card.position,
            "to_be_hidden": 1  # Se está ocultando (True = 1)
        })
        
        return HiddenSecret(
            playerId=target_player_id,
            secretId=secret_card.id,
            position=secret_card.position
        )
    
    def _apply_transfer_effect(
        self,
        secret_card: CardsXGame,
        from_player_id: int,
        to_player_id: int,
        game_id: int,
        action: ActionsPerTurn,
        executor_id: int
    ) -> TransferredSecret:
        """Transfiere un secreto de un jugador a otro (Satterthwaite con wildcard)"""
        # Obtener info de la carta
        card = crud.get_card_info_by_id(self.db, secret_card.id_card)
        
        # Calcular la nueva posición (máxima + 1 en el SECRET_SET del nuevo dueño)
        new_position = crud.get_max_position_for_player_secrets(
            self.db, game_id, to_player_id
        ) + 1
        
        # Transferir la carta (cambiar player_id, position, y hidden=True para face-down)
        crud.transfer_secret_card(
            self.db,
            card_id=secret_card.id,
            new_player_id=to_player_id,
            new_position=new_position,
            face_down=True
        )
        
        # Registrar la acción en ActionsPerTurn
        crud.create_action(self.db, {
            "id_game": action.id_game,
            "turn_id": action.turn_id,
            "player_id": executor_id,  # Quien ejecuta la acción
            "action_name": "transfer_secret",
            "action_type": ActionType.MOVE_CARD,  # Es un movimiento de carta
            "result": ActionResult.SUCCESS,
            "parent_action_id": action.id,
            "triggered_by_action_id": action.id,
            "player_source": from_player_id,  # Quien pierde el secreto
            "player_target": to_player_id,    # Quien recibe el secreto
            "secret_target": secret_card.id,
            "position_card": new_position,
            "to_be_hidden": 1  # Se transfiere face-down (oculto)
        })
        
        return TransferredSecret(
            fromPlayerId=from_player_id,
            toPlayerId=to_player_id,
            secretId=secret_card.id,
            cardId=card.id,
            cardName=card.name,
            imgSrc=card.img_src,
            faceDown=True,
            newPosition=new_position
        )

"""
Servicio para manejar la lógica de Dead Card Folly
"""
from sqlalchemy.orm import Session
from typing import Dict
from fastapi import HTTPException
from datetime import datetime
import logging

from ..db.models import (
    Game, Player, CardsXGame, ActionsPerTurn, Turn, Room,
    CardState, ActionType, ActionResult, ActionName, Direction
)
from ..db import crud
from ..schemas.dead_card_folly_schema import (
    PlayDeadCardFollyRequest,
    PlayDeadCardFollyResponse,
    SelectCardRequest,
    SelectCardResponse
)
from ..sockets.socket_service import get_websocket_service
from ..services.game_status_service import build_complete_game_state

logger = logging.getLogger(__name__)


class DeadCardFollyService:
    """Servicio para manejar la mecánica Dead Card Folly"""
    
    # ID de la carta Dead Card Folly
    DEAD_CARD_FOLLY_ID = 18
    
    def __init__(self, db: Session):
        self.db = db
    
    def play_dead_card_folly(
        self,
        room_id: int,
        request: PlayDeadCardFollyRequest
    ) -> PlayDeadCardFollyResponse:
        """
        Procesa el juego de la carta Dead Card Folly y elección de dirección.
        
        Validaciones:
        - Jugador existe y pertenece al juego
        - Es el turno del jugador (game.player_turn_id == player_id)
        - Room status == INGAME
        - Carta está en la mano del jugador
        - Carta es Dead Card Folly (id=18)

        Acciones:
        - Crea acción padre: EVENT_CARD con action_name=DEAD_CARD_FOLLY, result=PENDING
        - Guarda la dirección en la acción padre
        - Mueve carta al descarte
        - Notifica WebSocket: dead_card_folly_select_card
        - Actualiza estado público y privado
        
        Args:
            room_id: ID de la sala
            request: PlayDeadCardFollyRequest (player_id, card_id, direction)
        
        Returns:
            PlayDeadCardFollyResponse (success=True, action_id)
        
        Raises:
            HTTPException 400/403/404 si validación falla
        """
        game_id = self._get_game_id_from_room(room_id)
        player = self._get_player(request.player_id, game_id)
        
        game = crud.get_game_by_id(self.db, game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        
        if game.player_turn_id != player.id:
            raise HTTPException(
                status_code=403,
                detail="Not your turn"
            )
        
        room = crud.get_room_by_id(self.db, room_id)
        if not room or room.status != "INGAME":
            raise HTTPException(
                status_code=400,
                detail="Room is not in game"
            )
        
        # Validar que la carta está en la mano del jugador
        card_xgame = crud.get_card_xgame_by_id(self.db, request.card_id)
        if not card_xgame:
            raise HTTPException(status_code=404, detail="Card not found")
        
        if card_xgame.player_id != request.player_id or card_xgame.is_in != CardState.HAND:
            raise HTTPException(
                status_code=400,
                detail="Card not in player's hand"
            )
        
        # Validar que es carta Dead Card Folly
        card_info = crud.get_card_by_id(self.db, card_xgame.id_card)
        if not card_info or card_info.id != self.DEAD_CARD_FOLLY_ID:
            raise HTTPException(
                status_code=400,
                detail="Card is not Dead Card Folly"
            )
        
        # Obtener turno activo
        current_turn = crud.get_current_turn(self.db, game_id)
        if not current_turn:
            raise HTTPException(
                status_code=404,
                detail="No active turn found"
            )
        
        # Crear acción padre EVENT_CARD
        parent_action_data = {
            "id_game": game_id,
            "turn_id": current_turn.id,
            "player_id": request.player_id,
            "action_time": datetime.now(),
            "action_name": ActionName.DEAD_CARD_FOLLY,
            "action_type": ActionType.EVENT_CARD,
            "result": ActionResult.PENDING,
            "direction": request.direction,  # LEFT o RIGHT (ya es string por use_enum_values)
            "parent_action_id": None
        }
        
        parent_action = crud.create_action(self.db, parent_action_data)
        
        # Mover carta al descarte
        crud.move_card_to_discard(self.db, request.card_id, game_id)
        
        # Ocultar la carta que ahora está en position=2 (la que antes era tope)
        # La nueva carta está en position=1 con hidden=0
        # La que estaba en position=1 ahora está en position=2 y debe ser hidden=1
        previous_top_card = self.db.query(CardsXGame).filter(
            CardsXGame.id_game == game_id,
            CardsXGame.is_in == CardState.DISCARD,
            CardsXGame.position == 2
        ).first()
        
        if previous_top_card and not previous_top_card.hidden:
            previous_top_card.hidden = True
            self.db.flush()
            logger.debug(f"Hidden previous top card in discard (position 2)")
        
        self.db.commit()
        self.db.refresh(parent_action)
        
        logger.info(
            f"✅ Dead Card Folly played - "
            f"Player {request.player_id}, direction: {request.direction}, "
            f"action_id: {parent_action.id}"
        )
        
        # Notificaciones WebSocket y actualización de estado
        self._notify_card_played(room_id, game_id, player, parent_action, request.direction)
        
        return PlayDeadCardFollyResponse(
            success=True,
            action_id=parent_action.id
        )
    
    def select_card_for_exchange(
        self,
        room_id: int,
        request: SelectCardRequest
    ) -> SelectCardResponse:
        """
        Procesa la selección de carta de un jugador para el intercambio.
        
        Validaciones:
        - Acción padre existe y result == PENDING
        - Carta está en la mano del jugador
        - Jugador no ha seleccionado carta aún
        
        Acciones:
        - Crea acción hija CARD_EXCHANGE con selected_card_id
        - Si todas las selecciones están completas, ejecuta process_card_rotation
        
        Args:
            room_id: ID de la sala
            request: SelectCardRequest (action_id, card_id, player_id)
        
        Returns:
            SelectCardResponse con:
            - success: True
            - waiting: True si faltan selecciones, False si se completaron todas
            - pending_count: Número de jugadores que faltan seleccionar
            - message: Mensaje descriptivo
        
        Raises:
            HTTPException 400/404 si validación falla
        """

        game_id = self._get_game_id_from_room(room_id)
        player = self._get_player(request.player_id, game_id)
        
        # Obtener y validar acción padre
        parent_action = crud.get_action_by_id(self.db, request.action_id, game_id)
        if not parent_action:
            raise HTTPException(status_code=404, detail="Action not found")
        
        if parent_action.result != ActionResult.PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Action is not pending (current: {parent_action.result})"
            )
        
        # Validar que la carta está en la mano del jugador
        card_xgame = crud.get_card_xgame_by_id(self.db, request.card_id)
        if not card_xgame:
            raise HTTPException(status_code=404, detail="Card not found")
        
        if card_xgame.player_id != request.player_id or card_xgame.is_in != CardState.HAND:
            raise HTTPException(
                status_code=400,
                detail="Card not in player's hand"
            )
        
        # Validar que el jugador no ha seleccionado ya
        existing_selections = crud.get_actions_by_filters(
            self.db,
            parent_action_id=request.action_id
        )
        
        for selection in existing_selections:
            if selection.action_type == ActionType.CARD_EXCHANGE and selection.player_id == request.player_id:
                raise HTTPException(
                    status_code=400,
                    detail="Player has already selected a card"
                )
        
        # 6. Crear acción hija CARD_EXCHANGE
        # Guardamos card_given_id con el CardsXGame.id que el jugador seleccionó
        # Esto preserva el registro de qué carta física dio cada jugador
        # Estado PENDING hasta que se complete el intercambio
        child_action_data = {
            "id_game": game_id,
            "turn_id": parent_action.turn_id,
            "player_id": request.player_id,
            "action_time": datetime.now(),
            "action_name": ActionName.DEAD_CARD_FOLLY,
            "action_type": ActionType.CARD_EXCHANGE,
            "result": ActionResult.PENDING,  # PENDING hasta completar intercambio
            "parent_action_id": request.action_id,
            "card_given_id": request.card_id  # CardsXGame.id de la carta que da
        }
        
        child_action = crud.create_action(self.db, child_action_data)
        self.db.flush()
        
        # Verificar si ya todos seleccionaron
        room = crud.get_room_by_id(self.db, room_id)
        expected_selections = len(crud.list_players_by_room(self.db, room.id))
        
        # Contar solo las acciones hijas de tipo CARD_EXCHANGE
        all_child_actions = crud.get_actions_by_filters(
            self.db,
            parent_action_id=request.action_id
        )
        current_selections = len([
            action for action in all_child_actions 
            if action.action_type == ActionType.CARD_EXCHANGE
        ])
        
        pending_count = expected_selections - current_selections
        
        # Si todos seleccionaron, procesar rotación
        if pending_count == 0:
            self.process_card_rotation(parent_action)
            self.db.commit()
            
            logger.info(
                f"✅ All players selected cards - Rotation complete for action {request.action_id}"
            )
            
            # Notificaciones WebSocket y actualización de estado
            self._notify_rotation_complete(room_id, game_id, parent_action, expected_selections)
            
            return SelectCardResponse(
                success=True,
                waiting=False,
                pending_count=0,
                message="All players have selected their cards. Card rotation complete!"
            )
        
        # 9. Si faltan selecciones
        self.db.commit()
        
        logger.info(
            f"✅ Player {request.player_id} selected card - "
            f"Waiting for {pending_count} more players"
        )
        
        return SelectCardResponse(
            success=True,
            waiting=True,
            pending_count=pending_count,
            message=f"Waiting for {pending_count} more player(s) to select their cards"
        )
    
    def process_card_rotation(self, parent_action: ActionsPerTurn):
        """
        Ejecuta la rotación de cartas entre jugadores.
        
        Algoritmo:
        1. Obtiene todas las selecciones (acciones CARD_EXCHANGE)
        2. Para cada jugador, encuentra su vecino según dirección
        3. Intercambia id_card entre las CardsXGame correspondientes
        4. Actualiza cada acción hija con card_received_id
        5. Actualiza result de la acción padre a SUCCESS
        
        Args:
            parent_action: Acción padre EVENT_CARD con dirección
        
        Nota: Esta función NO hace commit, el llamador debe hacerlo
        """
        # 1. Obtener dirección de la acción padre
        direction = Direction(parent_action.direction)
        
        # 2. Obtener room_id del juego
        room = crud.get_room_by_game_id(self.db, parent_action.id_game)
        if not room:
            logger.error(f"Room not found for game {parent_action.id_game}")
            return
        
        # 3. Obtener todas las selecciones (acciones con tipo CARD_EXCHANGE)
        all_child_actions = crud.get_actions_by_filters(
            self.db,
            parent_action_id=parent_action.id
        )
        
        selections = [
            action for action in all_child_actions
            if action.action_type == ActionType.CARD_EXCHANGE
        ]
        
        if not selections:
            logger.warning(f"No selections found for action {parent_action.id}")
            return
        
        # 4. Construir mapa de player_id -> (action, card_given_id)
        player_data_map: Dict[int, tuple] = {}
        for selection in selections:
            player_data_map[selection.player_id] = (selection, selection.card_given_id)
        
        # 5. PASO 1: Guardar todos los id_card originales ANTES de modificar
        # Mapa: cardsXgame.id -> id_card original
        original_id_cards: Dict[int, int] = {}
        for player_id, (action, card_give_id) in player_data_map.items():
            card_xgame = crud.get_card_xgame_by_id(self.db, card_give_id)
            if card_xgame:
                original_id_cards[card_give_id] = card_xgame.id_card
        
        # 6. PASO 2: Para cada jugador, encontrar DE QUIÉN recibe (dirección inversa)
        # Lista de tuplas (card_xgame_obj, new_id_card, action)
        # 
        # Explicación:
        # - Si direction=LEFT, cada jugador DA a su vecino izquierdo
        # - Entonces cada jugador RECIBE de su vecino derecho (quien le da a él)
        # - Por eso invertimos la dirección para encontrar de quién recibimos
        inverse_direction = Direction.RIGHT if direction == Direction.LEFT else Direction.LEFT
        assignments = []
        
        for player_id, (action, card_give_id) in player_data_map.items():
            # Encontrar DE QUIÉN recibe (dirección inversa)
            donor = crud.get_player_neighbor_by_direction(
                self.db,
                player_id=player_id,
                room_id=room.id,
                direction=inverse_direction  # ← Invertida!
            )
            
            if not donor:
                logger.warning(f"No donor found for player {player_id}")
                continue
            
            # Obtener la carta que el donor seleccionó (la que este jugador recibirá)
            donor_data = player_data_map.get(donor.id)
            if not donor_data:
                logger.warning(f"No card selection found for donor {donor.id}")
                continue
            
            card_receive_id = donor_data[1]  # El card_given_id del donor
            
            # Obtener el id_card ORIGINAL de la carta que recibirá (antes de modificaciones)
            new_id_card = original_id_cards.get(card_receive_id)
            if new_id_card is None:
                logger.warning(f"No original id_card found for card {card_receive_id}")
                continue
            
            # Obtener el objeto CardsXGame que vamos a modificar
            card_xgame = crud.get_card_xgame_by_id(self.db, card_give_id)
            if not card_xgame:
                continue
            
            assignments.append((card_xgame, new_id_card, card_receive_id, action))
        
        # 7. PASO 3: Ejecutar todas las asignaciones simultáneamente
        for card_xgame, new_id_card, card_receive_id, action in assignments:
            # Asignar el nuevo id_card (el del vecino)
            old_id_card = card_xgame.id_card
            card_xgame.id_card = new_id_card
            
            # Actualizar la acción hija con card_received_id y marcar como SUCCESS
            action.card_received_id = card_receive_id
            action.result = ActionResult.SUCCESS
            
            logger.info(
                f"Player {action.player_id}: card_xgame={card_xgame.id} "
                f"changed id_card from {old_id_card} to {new_id_card} "
                f"(received from cardsXgame.id={card_receive_id})"
            )
        
        # Hacer flush de todos los cambios juntos
        self.db.flush()
        
        # 8. Actualizar acción padre a SUCCESS
        crud.update_action_result(self.db, parent_action.id, ActionResult.SUCCESS)
        
        logger.info(
            f"✅ Card rotation processed - "
            f"Action {parent_action.id}, {len(assignments)} cards rotated, "
            f"direction: {direction.value}"
        )
    
    # =============================
    # HELPERS
    # =============================
    
    def _get_game_id_from_room(self, room_id: int) -> int:
        """Obtiene el game_id desde el room_id"""
        room = crud.get_room_by_id(self.db, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        
        if not room.id_game:
            raise HTTPException(status_code=400, detail="Room has no active game")
        
        return room.id_game
    
    def _get_player(self, player_id: int, game_id: int) -> Player:
        """Valida que el jugador existe y pertenece al juego"""
        player = crud.get_player_by_id(self.db, player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        # Verificar que el jugador pertenece a una room de este juego
        if not player.room or player.room.id_game != game_id:
            raise HTTPException(
                status_code=403,
                detail="Player does not belong to this game"
            )
        
        return player
    
    def _notify_card_played(
        self,
        room_id: int,
        game_id: int,
        player: Player,
        parent_action: ActionsPerTurn,
        direction: Direction
    ):
        """
        Notifica que se jugó Dead Card Folly y actualiza estados.
        
        Emite:
        - WebSocket: dead_card_folly_select_card
        - Estado público: actualiza descarte
        - Estado privado: actualiza mano del jugador
        """
        import asyncio
        
        ws_service = get_websocket_service()
        
        # 1. Notificación WebSocket: todos deben seleccionar carta
        asyncio.create_task(
            ws_service.notificar_dead_card_folly_select_card(
                room_id=room_id,
                action_id=parent_action.id,
                direction=direction,  # Ya es string
                player_id=player.id,
                player_name=player.name
            )
        )
        
        # 2. Actualizar estado del juego
        game_state = build_complete_game_state(self.db, game_id)
        
        # 3. Notificar estado público (actualiza descarte)
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
        
        logger.info(f"📡 Notified Dead Card Folly card played to room {room_id}")
    
    def _notify_rotation_complete(
        self,
        room_id: int,
        game_id: int,
        parent_action: ActionsPerTurn,
        players_count: int
    ):
        """
        Notifica que el intercambio se completó y actualiza estados.
        
        Emite:
        - WebSocket: dead_card_folly_complete
        - Estado público: por si acaso
        - Estado privado: actualiza manos de todos los jugadores
        """
        import asyncio
        
        ws_service = get_websocket_service()
        
        # 1. Notificación WebSocket: intercambio completado
        asyncio.create_task(
            ws_service.notificar_dead_card_folly_complete(
                room_id=room_id,
                action_id=parent_action.id,
                direction=parent_action.direction,
                players_count=players_count
            )
        )
        
        # 2. Actualizar estado del juego
        game_state = build_complete_game_state(self.db, game_id)
        
        # 3. Notificar estado público (por si acaso, no debería cambiar)
        asyncio.create_task(
            ws_service.notificar_estado_publico(
                room_id=room_id,
                game_state=game_state
            )
        )
        
        # 4. Notificar estados privados (actualiza manos de TODOS los jugadores)
        if game_state.get("estados_privados"):
            asyncio.create_task(
                ws_service.notificar_estados_privados(
                    room_id=room_id,
                    estados_privados=game_state["estados_privados"]
                )
            )
        
        logger.info(f"📡 Notified Dead Card Folly rotation complete to room {room_id}")

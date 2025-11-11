"""
Servicio para manejar la lógica de Not So Fast (NSF)
"""
from sqlalchemy.orm import Session
from typing import List, Tuple, Optional
from fastapi import HTTPException
from datetime import datetime, timedelta
import logging

from ..db.models import (
    Game, Player, CardsXGame, ActionsPerTurn, Turn, Room,
    CardState, ActionType, ActionResult, ActionName, CardType
)
from ..db import crud
from ..schemas.not_so_fast_schema import StartActionRequest, StartActionResponse

logger = logging.getLogger(__name__)


class NotSoFastService:
    """Servicio para manejar la mecánica Not So Fast"""
    
    # IDs de cartas importantes
    NOT_SO_FAST_CARD_ID = 13
    CARDS_OFF_THE_TABLE_ID = 24
    BLACKMAILED_ID = 14
    TOMMY_BERESFORD_ID = 8
    TUPPENCE_BERESFORD_ID = 10
    HARLEY_QUIN_CARD_ID = 4
    ARIADNE_OLIVER_CARD_ID = 5
    EILEEN_BRENT_CARD_ID = 9
    
    # Tiempo de ventana NSF en segundos
    NSF_WINDOW_DURATION = 10
    
    def __init__(self, db: Session):
        self.db = db
    
    def start_action(
        self,
        room_id: int,
        request: StartActionRequest
    ) -> StartActionResponse:
        """
        Procesa el inicio de una acción que puede ser contrarrestada con NSF.
        
        Returns:
            StartActionResponse con actionId, actionNSFId, cancellable, timeRemaining
        
        Raises:
            HTTPException con códigos 400, 403, 404
        """
        # 1. Obtener game_id desde room_id
        game_id = self._get_game_id_from_room(room_id)
        
        # 2. Validar que la acción es válida según el tipo
        self._validate_action(
            game_id=game_id,
            player_id=request.playerId,
            card_ids=request.cardIds,
            action_type=request.additionalData.actionType,
            set_position=request.additionalData.setPosition
        )
        
        # 3. Obtener el turno actual
        current_turn = crud.get_active_turn_for_player(self.db, game_id, request.playerId)
        if not current_turn:
            raise HTTPException(
                status_code=404,
                detail="No active turn found for player"
            )
        
        # 4. Chequear si hay jugadores con NSF en mano
        players_with_nsf = self._check_players_have_nsf(game_id, request.playerId)
        
        # 5. Chequear si la acción es cancelable (por tipo)
        action_is_cancellable = self._check_action_is_cancellable(
            card_ids=request.cardIds,
            action_type=request.additionalData.actionType,
            set_position=request.additionalData.setPosition,
            game_id=game_id,
            player_id=request.playerId
        )
        
        # 6. Determinar si se activa NSF (cancelable Y hay jugadores con NSF)
        cancellable = action_is_cancellable and players_with_nsf
        
        # 7. Crear la acción de intención 
        intention_action = self._create_intention_action(
            game_id=game_id,
            turn_id=current_turn.id,
            player_id=request.playerId,
            card_ids=request.cardIds,
            action_type=request.additionalData.actionType
        )
        
        # 8. Si es cancelable, crear la acción NSF 
        nsf_action_id = None
        time_remaining = None
        
        if cancellable:
            nsf_action = self._create_nsf_start_action(
                game_id=game_id,
                turn_id=current_turn.id,
                player_id=request.playerId,
                triggered_by_action_id=intention_action.id
            )
            nsf_action_id = nsf_action.id
            time_remaining = self.NSF_WINDOW_DURATION
        else:
            # Si no es cancelable, marcar la intención como CONTINUE
            crud.update_action_result(self.db, intention_action.id, ActionResult.CONTINUE)
        
        # 9. Commit
        self.db.commit()
        
        return StartActionResponse(
            actionId=intention_action.id,
            actionNSFId=nsf_action_id,
            cancellable=cancellable,
            timeRemaining=time_remaining
        )
    
    # =============================
    # VALIDACIONES
    # =============================
    
    def _validate_action(
        self,
        game_id: int,
        player_id: int,
        card_ids: List[int],
        action_type: str,
        set_position: Optional[int]
    ):
        """
        Valida que la acción es válida según el tipo.
        
        Raises:
            HTTPException si la acción no es válida
        """
        # Validar que el jugador existe y pertenece al juego
        player = self._get_player(player_id, game_id)
        
        # Validar que es el turno del jugador
        game = crud.get_game_by_id(self.db, game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        
        if game.player_turn_id != player.id:
            raise HTTPException(
                status_code=403,
                detail="Not your turn"
            )
        
        # Validar según el tipo de acción
        if action_type == "EVENT":
            self._validate_event_action(card_ids, player_id, game_id)
        
        elif action_type == "CREATE_SET":
            self._validate_create_set_action(card_ids, player_id, game_id)
        
        elif action_type == "ADD_TO_SET":
            self._validate_add_to_set_action(card_ids, player_id, game_id, set_position)
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action type: {action_type}"
            )
    
    def _validate_event_action(self, card_ids: List[int], player_id: int, game_id: int):
        """Valida que la acción EVENT es válida"""
        # Debe ser exactamente 1 carta
        if len(card_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail="Event action requires exactly 1 card"
            )
        
        # Obtener la carta y validar que está en la mano del jugador
        cards = crud.get_cards_in_hand_by_ids(self.db, card_ids, player_id, game_id)
        if len(cards) != 1:
            raise HTTPException(
                status_code=400,
                detail="Card not in player's hand"
            )
        
        card = cards[0]
        
        # Validar que es una carta de tipo EVENT
        card_info = crud.get_card_by_id(self.db, card.id_card)
        if not card_info or card_info.type != CardType.EVENT:
            raise HTTPException(
                status_code=400,
                detail="Card is not an event card"
            )
    
    def _validate_create_set_action(self, card_ids: List[int], player_id: int, game_id: int):
        """Valida que la acción CREATE_SET es válida (reutiliza lógica de detective_set_service)"""
        # Debe tener al menos 2 cartas
        if len(card_ids) < 2:
            raise HTTPException(
                status_code=400,
                detail="Detective set requires at least 2 cards"
            )
        
        # Validar que todas las cartas están en la mano del jugador
        cards = crud.get_cards_in_hand_by_ids(self.db, card_ids, player_id, game_id)
        if len(cards) != len(card_ids):
            raise HTTPException(
                status_code=400,
                detail="Some cards are not in player's hand"
            )
        
        # Validar que todas son cartas DETECTIVE
        for card in cards:
            card_info = crud.get_card_by_id(self.db, card.id_card)
            if not card_info or card_info.type != CardType.DETECTIVE:
                raise HTTPException(
                    status_code=400,
                    detail="All cards must be detective cards to create a set"
                )
        
        # Nota: La validación completa de combinación de set se hace en detective_set_service
        # Aquí solo validamos lo básico para NSF
    
    def _validate_add_to_set_action(
        self,
        card_ids: List[int],
        player_id: int,
        game_id: int,
        set_position: Optional[int]
    ):
        """Valida que la acción ADD_TO_SET es válida"""
        # Debe ser exactamente 1 carta
        if len(card_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail="Add to set action requires exactly 1 card"
            )
        
        # Validar que la carta está en la mano del jugador
        cards = crud.get_cards_in_hand_by_ids(self.db, card_ids, player_id, game_id)
        if len(cards) != 1:
            raise HTTPException(
                status_code=400,
                detail="Card not in player's hand"
            )
        
        card = cards[0]
        
        # Validar que es una carta DETECTIVE
        card_info = crud.get_card_by_id(self.db, card.id_card)
        if not card_info or card_info.type != CardType.DETECTIVE:
            raise HTTPException(
                status_code=400,
                detail="Card must be a detective card"
            )
        
        # Validar que NO es comodín Harley Quin
        if card.id_card == self.HARLEY_QUIN_CARD_ID:
            raise HTTPException(
                status_code=400,
                detail="Harley Quin wildcards cannot be added to existing sets"
            )
        
        # Si es Ariadne Oliver, NO requiere setPosition (se elige después el jugador/set objetivo)
        if card.id_card == self.ARIADNE_OLIVER_CARD_ID:
            # Oliver puede agregarse a cualquier set, se validará en otro endpoint
            return
        
        # Para otras cartas detective, setPosition es OBLIGATORIO
        if set_position is None:
            raise HTTPException(
                status_code=400,
                detail="setPosition is required for ADD_TO_SET action (except for Ariadne Oliver)"
            )
        
        # Validar que el set existe
        set_cards = self.db.query(CardsXGame).filter(
            CardsXGame.id_game == game_id,
            CardsXGame.player_id == player_id,
            CardsXGame.is_in == CardState.DETECTIVE_SET,
            CardsXGame.position == set_position
        ).count()
        
        if set_cards == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No detective set found at position {set_position}"
            )
    
    # =============================
    # CHEQUEOS NSF
    # =============================
    
    def _check_players_have_nsf(self, game_id: int, exclude_player_id: int) -> bool:
        """
        Verifica si hay jugadores (excepto el activo) que tienen NSF en mano.
        
        Returns:
            True si al menos un jugador tiene NSF, False en caso contrario
        """
        # Obtener todos los jugadores del juego (excepto el activo)
        room = crud.get_room_by_game_id(self.db, game_id)
        if not room:
            return False
        
        players = crud.list_players_by_room(self.db, room.id)
        other_player_ids = [p.id for p in players if p.id != exclude_player_id]
        
        if not other_player_ids:
            return False
        
        # Buscar si alguno tiene NSF en mano
        nsf_count = self.db.query(CardsXGame).filter(
            CardsXGame.id_game == game_id,
            CardsXGame.player_id.in_(other_player_ids),
            CardsXGame.is_in == CardState.HAND,
            CardsXGame.id_card == self.NOT_SO_FAST_CARD_ID
        ).count()
        
        return nsf_count > 0
    
    def _check_action_is_cancellable(
        self,
        card_ids: List[int],
        action_type: str,
        set_position: Optional[int],
        game_id: int,
        player_id: int
    ) -> bool:
        """
        Determina si la acción es cancelable según las reglas del juego.
        
        Returns:
            True si la acción es cancelable, False en caso contrario
        """
        if action_type == "EVENT":
            return self._is_event_cancellable(card_ids, game_id)
        
        elif action_type == "CREATE_SET":
            return self._is_create_set_cancellable(card_ids, game_id)
        
        elif action_type == "ADD_TO_SET":
            return self._is_add_to_set_cancellable(card_ids, set_position, game_id, player_id)
        
        return False
    
    def _is_event_cancellable(self, card_ids: List[int], game_id: int) -> bool:
        """
        Verifica si una carta evento es cancelable.
        
        NO cancelables:
        - Cards off the table (id=24)
        """
        card = self.db.query(CardsXGame).filter(
            CardsXGame.id.in_(card_ids),
            CardsXGame.id_game == game_id
        ).first()
        
        if not card:
            return False
        
        # Cards off the table NO es cancelable
        if card.id_card == self.CARDS_OFF_THE_TABLE_ID:
            return False
        
        # Todas las demás cartas evento SON cancelables
        return True
    
    def _is_create_set_cancellable(self, card_ids: List[int], game_id: int) -> bool:
        """
        Verifica si crear un set es cancelable.
        
        NO cancelable si:
        - El set tiene ambos hermanos Beresford (Tommy id=8 Y Tuppence id=10)
        """
        # Obtener las cartas del set
        cards = self.db.query(CardsXGame).filter(
            CardsXGame.id.in_(card_ids),
            CardsXGame.id_game == game_id
        ).all()
        
        if not cards:
            return True
        
        # Obtener los id_card (sin contar comodines)
        card_types = [c.id_card for c in cards if c.id_card != self.HARLEY_QUIN_CARD_ID]
        
        # Verificar si tiene ambos hermanos
        has_tommy = self.TOMMY_BERESFORD_ID in card_types
        has_tuppence = self.TUPPENCE_BERESFORD_ID in card_types
        
        # NO cancelable si tiene ambos hermanos
        if has_tommy and has_tuppence:
            return False
        
        # Cancelable en todos los demás casos
        return True
    
    def _is_add_to_set_cancellable(
        self,
        card_ids: List[int],
        set_position: int,
        game_id: int,
        player_id: int
    ) -> bool:
        """
        Verifica si agregar una carta a un set es cancelable.
        
        NO cancelable si:
        - La carta a agregar es Tommy (8) o Tuppence (10)
        - Y el set resultante tendría ambos hermanos
        """
        # Obtener la carta a agregar
        new_card = self.db.query(CardsXGame).filter(
            CardsXGame.id.in_(card_ids),
            CardsXGame.id_game == game_id
        ).first()
        
        if not new_card:
            return True
        
        # Si la carta a agregar NO es Tommy ni Tuppence, es cancelable
        if new_card.id_card not in [self.TOMMY_BERESFORD_ID, self.TUPPENCE_BERESFORD_ID]:
            return True
        
        # Obtener las cartas del set existente
        existing_set_cards = self.db.query(CardsXGame).filter(
            CardsXGame.id_game == game_id,
            CardsXGame.player_id == player_id,
            CardsXGame.is_in == CardState.DETECTIVE_SET,
            CardsXGame.position == set_position
        ).all()
        
        # Obtener los id_card del set (sin comodines)
        set_card_types = [c.id_card for c in existing_set_cards if c.id_card != self.HARLEY_QUIN_CARD_ID]
        
        # Verificar si el set ya tiene el hermano contrario
        if new_card.id_card == self.TOMMY_BERESFORD_ID:
            # Agregando Tommy, verificar si el set tiene Tuppence
            if self.TUPPENCE_BERESFORD_ID in set_card_types:
                return False  # Set resultante tendría ambos hermanos
        
        elif new_card.id_card == self.TUPPENCE_BERESFORD_ID:
            # Agregando Tuppence, verificar si el set tiene Tommy
            if self.TOMMY_BERESFORD_ID in set_card_types:
                return False  # Set resultante tendría ambos hermanos
        
        # Cancelable en todos los demás casos
        return True
    
    # =============================
    # CREACIÓN DE ACCIONES
    # =============================
    
    def _create_intention_action(
        self,
        game_id: int,
        turn_id: int,
        player_id: int,
        card_ids: List[int],
        action_type: str
    ) -> ActionsPerTurn:
        """
        Crea la acción de intención
        
        Esta acción representa la intención de realizar una jugada.
        """
        # Determinar el action_name según el tipo de acción y las cartas
        action_name = self._determine_action_name(card_ids, action_type, game_id)
        
        action_data = {
            "id_game": game_id,
            "turn_id": turn_id,
            "player_id": player_id,
            "action_time": datetime.now(),
            "action_name": action_name,
            "action_type": ActionType.INIT,
            "result": ActionResult.PENDING,
            "parent_action_id": None,
            "triggered_by_action_id": None
        }
        
        return crud.create_action(self.db, action_data)
    
    def _create_nsf_start_action(
        self,
        game_id: int,
        turn_id: int,
        player_id: int,
        triggered_by_action_id: int
    ) -> ActionsPerTurn:
        """
        Crea la acción NSF de inicio.
        
        Esta acción representa el inicio de la ventana NSF.
        """
        action_time_end = datetime.now() + timedelta(seconds=self.NSF_WINDOW_DURATION)
        
        action_data = {
            "id_game": game_id,
            "turn_id": turn_id,
            "player_id": player_id,
            "action_time": datetime.now(),
            "action_time_end": action_time_end,
            "action_name": ActionName.INSTANT_START,
            "action_type": ActionType.INSTANT,
            "result": ActionResult.PENDING,
            "parent_action_id": None,
            "triggered_by_action_id": triggered_by_action_id
        }
        
        return crud.create_action(self.db, action_data)
    
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
    
    def _determine_action_name(
        self,
        card_ids: List[int],
        action_type: str,
        game_id: int
    ) -> str:
        """Determina el nombre de la acción según las cartas jugadas"""
        if action_type == "EVENT":
            # Para eventos, usar el nombre de la carta
            card = self.db.query(CardsXGame).filter(
                CardsXGame.id.in_(card_ids),
                CardsXGame.id_game == game_id
            ).first()
            
            if card:
                card_info = crud.get_card_by_id(self.db, card.id_card)
                if card_info:
                    return card_info.name
        
        elif action_type == "CREATE_SET":
            return "Create Detective Set"
        
        elif action_type == "ADD_TO_SET":
            return "Add Detective to Set"
        
        return "Unknown Action"
    
    def play_nsf_card(
        self,
        room_id: int,
        action_id: int,
        player_id: int,
        card_id: int
    ) -> Tuple[int, int, str]:
        """
        Procesa el juego de una carta Not So Fast.
        
        Args:
            room_id: ID de la sala
            action_id: ID de la acción original siendo contrarrestada
            player_id: ID del jugador que juega NSF
            card_id: ID de la carta NSF en cardsXgame
        
        Returns:
            Tupla (nsf_action_id, nsf_start_action_id, player_name)
            - nsf_action_id: ID de la acción de INIT creada
            - nsf_start_action_id: ID de la acción de NSF_START actualizada
            - player_name: Nombre del jugador para el mensaje
        
        Raises:
            HTTPException con códigos 400, 403, 404
        """
        # 1. Obtener game_id y validar room
        game_id = self._get_game_id_from_room(room_id)
        
        # 2. Validar jugador
        player = self._get_player(player_id, game_id)
        
        # 3. Validar que la carta NSF está en la mano del jugador
        player_cards = crud.list_cards_by_player(self.db, player_id, game_id)
        
        # Buscar si tiene la carta NSF en mano
        nsf_card = None
        for card in player_cards:
            if card.id == card_id and card.is_in == CardState.HAND:
                nsf_card = card
                break
        
        if not nsf_card:
            raise HTTPException(
                status_code=400,
                detail="NSF card not found in player's hand"
            )
        
        # 4. Validar que es una carta NSF (id=13)
        card_info = crud.get_card_by_id(self.db, nsf_card.id_card)
        if not card_info or card_info.id != self.NOT_SO_FAST_CARD_ID:
            raise HTTPException(
                status_code=400,
                detail="Card is not a Not So Fast card"
            )
        
        # 5. Obtener la acción original 
        original_action = crud.get_action_by_id(self.db, action_id, game_id)
        
        if not original_action:
            raise HTTPException(
                status_code=404,
                detail="Original action not found"
            )
        
        # 6. Obtener la acción NSF_START 
        nsf_start_action = crud.get_nsf_start_action(
            self.db,
            triggered_by_action_id=action_id,
            game_id=game_id
        )
        
        if not nsf_start_action:
            raise HTTPException(
                status_code=400,
                detail="NSF window not active for this action"
            )
        
        # 7. Crear la acción NSF_PLAY y actualizar la acción NSF_START
        now = datetime.now()
        action_time_end = now + timedelta(seconds=self.NSF_WINDOW_DURATION)
        
        # Crear acción NSF_PLAY
        nsf_play_action = crud.create_nsf_play_action(
            db=self.db,
            game_id=game_id,
            turn_id=original_action.turn_id,
            player_id=player_id,
            nsf_start_action_id=nsf_start_action.id,
            original_action_id=action_id,
            card_id=card_id,
            action_time_end=action_time_end
        )
        
        # Actualizar action_time_end de YYY
        crud.update_action_time_end(self.db, nsf_start_action.id, action_time_end)
        
        # 8. Commit final
        self.db.commit()
        self.db.refresh(nsf_play_action)
        self.db.refresh(nsf_start_action)
        
        return (
            nsf_play_action.id,
            nsf_start_action.id,
            player.name
        )
    
    def cancel_nsf_action(
        self,
        room_id: int,
        action_id: int,
        player_id: int,
        card_ids: List[int],
        additional_data: dict
    ) -> str:
        """
        Ejecuta una acción cancelada por NSF sin efectos.
        
        Tres casos:
        1. CREATE_SET: Crea el set pero sin ejecutar efecto (excepto Eileen Brent)
        2. EVENT: Mueve carta al discard debajo de las NSF
        3. ADD_TO_SET: Agrega carta al set pero sin efecto
        
        Args:
            room_id: ID de la sala
            action_id: ID de la acción original (XXX) que fue cancelada
            player_id: ID del jugador que inició la acción
            card_ids: Lista de cardsXgame.id involucrados
            additional_data: Dict con actionType, player_target, setPosition
        
        Returns:
            str: Mensaje descriptivo de lo que ocurrió
        
        Raises:
            HTTPException con códigos 400, 404
        """
        # 1. Validaciones iniciales
        game_id = self._get_game_id_from_room(room_id)
        player = self._get_player(player_id, game_id)
        
        # 2. Validar que la acción existe y está CANCELADA
        action = crud.get_action_by_id(self.db, action_id, game_id)
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        
        if action.result != ActionResult.CANCELLED:
            raise HTTPException(
                status_code=400,
                detail=f"Action must be CANCELLED (current: {action.result})"
            )
        
        # 3. Procesar según tipo de acción
        action_type = additional_data.get("actionType")
        
        if action_type == "CREATE_SET":
            return self._cancel_create_set(game_id, player_id, card_ids, player.name)
        
        elif action_type == "EVENT":
            return self._cancel_event(game_id, action_id, card_ids, player.name)
        
        elif action_type == "ADD_TO_SET":
            return self._cancel_add_to_set(
                game_id, player_id, card_ids, additional_data, player.name
            )
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid actionType: {action_type}"
            )
    
    def _cancel_create_set(
        self,
        game_id: int,
        player_id: int,
        card_ids: List[int],
        player_name: str
    ) -> str:
        """
        Caso 1: CREATE_SET cancelado.
        
        - Si contiene Eileen Brent (id=9): Las cartas quedan en HAND (no pasa nada)
        - Si no: Crea el set pero SIN ejecutar efecto
        
        Mensajes:
        - Con Eileen: "El jugador {name} jugó bajar set de detective pero fue cancelado por NSF. 
                       Set creado de Eileen vuelve a la mano del jugador {name}"
        - Sin Eileen: "El jugador {name} jugó bajar set de detective pero fue cancelado por NSF. 
                       Set de {nombre de detective} creado pero efecto no realizado"
        """
        # Verificar si alguna carta es Eileen Brent (id_card == 9)
        if crud.check_set_contains_card(self.db, card_ids, self.EILEEN_BRENT_CARD_ID):
            logger.info(
                f"Eileen Brent detected in cancelled CREATE_SET - "
                f"Cards stay in hand for player {player_id}"
            )
            return (
                f"El jugador {player_name} jugó bajar set de detective pero fue cancelado por NSF. "
                f"Set creado de Eileen vuelve a la mano del jugador {player_name}"
            )
        
        # Obtener las cartas (validar que están en HAND)
        cards = crud.get_cards_in_hand_by_ids(self.db, card_ids, player_id, game_id)
        if len(cards) != len(card_ids):
            raise HTTPException(
                status_code=400,
                detail="Some cards are not in player's hand"
            )
        
        # Obtener siguiente posición de set
        next_position = crud.get_max_position_for_player_by_state(
            self.db, game_id, player_id, CardState.DETECTIVE_SET
        ) + 1
        
        # Mover cartas a DETECTIVE_SET
        crud.update_cards_state(
            self.db, 
            cards, 
            CardState.DETECTIVE_SET, 
            next_position, 
            hidden=False
        )
        
        # Obtener nombre del detective del set
        detective_name = crud.get_detective_set_name(self.db, card_ids)
        
        logger.info(
            f"✅ CREATE_SET cancelled executed - "
            f"Player {player_id}, detective: {detective_name}, position: {next_position}"
        )
        
        return (
            f"El jugador {player_name} jugó bajar set de detective pero fue cancelado por NSF. "
            f"Set de {detective_name} creado pero efecto no realizado"
        )
    
    def _cancel_event(
        self,
        game_id: int,
        action_id: int,
        card_ids: List[int],
        player_name: str
    ) -> str:
        """
        Caso 2: EVENT cancelado.
        
        Mueve la carta al discard DEBAJO de todas las NSF jugadas.
        
        Mensaje:
        "El jugador {name} jugó carta evento pero fue cancelado por NSF. 
         La carta {nombre de la carta} se encuentra ahora en el mazo de descarte."
        """
        if len(card_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail="EVENT actions should have exactly 1 card"
            )
        
        card_xgame_id = card_ids[0]
        
        # Obtener la acción XXX y buscar YYY
        action_xxx = crud.get_action_by_id(self.db, action_id, game_id)
        nsf_start_action = crud.get_nsf_start_action(
            self.db, 
            triggered_by_action_id=action_xxx.id,
            game_id=game_id
        )
        
        if not nsf_start_action:
            raise HTTPException(
                status_code=400,
                detail="NSF start action not found for this action"
            )
        
        # Contar cuántas NSF se jugaron (acciones ZZZ)
        nsf_chain = crud.get_actions_by_filters(
            self.db,
            parent_action_id=nsf_start_action.id,
            triggered_by_action_id=action_xxx.id
        )
        nsf_count = len(nsf_chain)
        
        # La carta va DEBAJO de las NSF (position = nsf_count + 1)
        target_position = nsf_count + 1
        
        # Incrementar posiciones de cartas antiguas en discard
        crud.increment_discard_positions_from(self.db, game_id, target_position)
        
        # Obtener info de la carta para el mensaje
        card_xgame = crud.get_card_xgame_by_id(self.db, card_xgame_id)
        if not card_xgame:
            raise HTTPException(status_code=404, detail="Card not found")
        
        # Obtener nombre de la carta desde tabla Card
        card_name = crud.get_card_name(self.db, card_xgame.id_card)
        
        # Mover carta al discard
        crud.update_single_card_state(
            self.db,
            card_xgame_id=card_xgame_id,
            new_state=CardState.DISCARD,
            new_position=target_position,
            player_id=None,
            hidden=False
        )
        
        logger.info(
            f"✅ EVENT cancelled executed - "
            f"Card: {card_name}, Position: {target_position} (below {nsf_count} NSF)"
        )
        
        return (
            f"El jugador {player_name} jugó carta evento pero fue cancelado por NSF. "
            f"La carta {card_name} se encuentra ahora en el mazo de descarte."
        )
    
    def _cancel_add_to_set(
        self,
        game_id: int,
        player_id: int,
        card_ids: List[int],
        additional_data: dict,
        player_name: str
    ) -> str:
        """
        Caso 3: ADD_TO_SET cancelado.
        
        Tres subcasos:
        - Ariadne Oliver (id=5): Agrega a set ajeno
        - Eileen Brent (id=9): La carta queda en HAND
        - Otros: Agrega a set propio
        
        Mensajes:
        - Caso 4 (normal): "El jugador {name} jugó agregar carta a set de detective pero fue cancelado por NSF. 
                            Set de {nombre de detective} ampliado pero efecto no realizado"
        - Caso 5 (Eileen): "El jugador {name} jugó agregar carta a set de detective pero fue cancelado por NSF. 
                            La carta Eileen vuelve a la mano del jugador {name}"
        - Caso 6 (Oliver): "El jugador {name} jugó agregar carta a set de detective pero fue cancelado por NSF. 
                            Oliver agregada a set {nombre del detective del set} del jugador {nombre}, no se realiza su efecto."
        """
        if len(card_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail="ADD_TO_SET actions should have exactly 1 card"
            )
        
        card_xgame_id = card_ids[0]
        
        # Obtener la carta
        card_xgame = crud.get_card_xgame_by_id(self.db, card_xgame_id)
        if not card_xgame:
            raise HTTPException(status_code=404, detail="Card not found")
        
        card_info = crud.get_card_by_id(self.db, card_xgame.id_card)
        if not card_info:
            raise HTTPException(status_code=404, detail="Card info not found")
        
        card_name = card_info.name
        
        # SUBCASO 5: Eileen Brent - la carta queda en HAND
        if card_info.id == self.EILEEN_BRENT_CARD_ID:
            logger.info(
                f"🚫 Eileen Brent in ADD_TO_SET cancelled - "
                f"Card stays in hand for player {player_id}"
            )
            return (
                f"El jugador {player_name} jugó agregar carta a set de detective pero fue cancelado por NSF. "
                f"La carta Eileen vuelve a la mano del jugador {player_name}"
            )
        
        # SUBCASO 6: Ariadne Oliver - agregar a set ajeno
        if card_info.id == self.ARIADNE_OLIVER_CARD_ID:
            player_target = additional_data.get("player_target")
            set_position = additional_data.get("setPosition")
            
            if not player_target or not set_position:
                raise HTTPException(
                    status_code=400,
                    detail="Ariadne Oliver requires player_target and setPosition"
                )
            
            # Validar que el set existe
            target_set = crud.get_detective_set_cards_by_position(
                self.db, game_id, player_target, set_position
            )
            if not target_set:
                raise HTTPException(status_code=404, detail="Target set not found")
            
            # Obtener nombre del detective del set
            target_set_ids = [card.id for card in target_set]
            detective_name = crud.get_detective_set_name(self.db, target_set_ids)
            
            # Obtener nombre del jugador dueño del set
            target_player_name = crud.get_player_name(self.db, player_target)
            
            # Agregar carta al set ajeno
            crud.update_single_card_state(
                self.db,
                card_xgame_id=card_xgame_id,
                new_state=CardState.DETECTIVE_SET,
                new_position=set_position,
                player_id=player_target,  # Ahora pertenece al otro jugador
                hidden=False
            )
            
            logger.info(
                f"✅ ADD_TO_SET (Ariadne Oliver) cancelled executed - "
                f"Card added to player {player_target}'s set at position {set_position}"
            )
            
            return (
                f"El jugador {player_name} jugó agregar carta a set de detective pero fue cancelado por NSF. "
                f"Oliver agregada a set {detective_name} del jugador {target_player_name}, no se realiza su efecto."
            )
        
        # SUBCASO 4: Otros detectives - agregar a set propio
        set_position = additional_data.get("setPosition")
        if not set_position:
            raise HTTPException(status_code=400, detail="setPosition required")
        
        # Validar player_target si viene (debería ser el mismo jugador)
        player_target = additional_data.get("player_target")
        if player_target and player_target != player_id:
            raise HTTPException(
                status_code=400,
                detail="Non-Ariadne cards can only be added to own sets"
            )
        
        # Validar que el set existe
        target_set = crud.get_detective_set_cards_by_position(
            self.db, game_id, player_id, set_position
        )
        if not target_set:
            raise HTTPException(status_code=404, detail="Set not found")
        
        # Obtener nombre del detective del set
        target_set_ids = [card.id for card in target_set]
        detective_name = crud.get_detective_set_name(self.db, target_set_ids)
        
        # Agregar carta al set propio
        crud.update_single_card_state(
            self.db,
            card_xgame_id=card_xgame_id,
            new_state=CardState.DETECTIVE_SET,
            new_position=set_position,
            player_id=player_id,
            hidden=False
        )
        
        logger.info(
            f"✅ ADD_TO_SET cancelled executed - "
            f"Card {card_name} added to own set at position {set_position}"
        )
        
        return (
            f"El jugador {player_name} jugó agregar carta a set de detective pero fue cancelado por NSF. "
            f"Set de {detective_name} ampliado pero efecto no realizado"
        )

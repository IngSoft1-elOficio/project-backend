from sqlalchemy.orm import Session
from typing import List, Tuple
from fastapi import HTTPException

from ..db.models import (
    Game, Player, CardsXGame, ActionsPerTurn, Turn,
    CardState, ActionType, ActionResult
)
from ..db import crud
from ..schemas.detective_set_schema import (
    SetType, PlayDetectiveSetRequest, NextActionType, 
    NextAction, NextActionMetadata, SecretInfo, SET_MIN_CARDS, SET_ACTION_NAMES
)


class DetectiveSetService:
    """Servicio para manejar la lógica de bajar sets de detectives"""
    
    # IDs de cartas detective
    HARLEY_QUIN_CARD_ID = 4  
    TOMMY_BERESFORD_CARD_ID = 8
    TUPPENCE_BERESFORD_CARD_ID = 10
    
    # Mapeo de setType a id_card esperado
    SET_CARD_IDS = {
        SetType.POIROT: 11,           # Hercule Poirot
        SetType.MARPLE: 6,            # Miss Marple
        SetType.SATTERTHWAITE: 12,    # Mr Satterthwaite
        SetType.PYNE: 7,              # Parker Pyne
        SetType.EILEENBRENT: 9,       # Lady Eileen "Bundle" Brent
        # BERESFORD es especial: acepta 8 (Tommy) o 10 (Tuppence)
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def play_detective_set(
        self, 
        game_id: int, 
        request: PlayDetectiveSetRequest
    ) -> Tuple[int, NextAction]:
        """
        Procesa la jugada de bajar un set de detectives.
        
        Returns:
            Tuple[action_id, next_action]
        
        Raises:
            HTTPException con códigos 400, 403, 404, 409
        """
        # 1. Validar que el juego existe
        game = self._get_game(game_id)
        
        # 2. Validar que el jugador existe y pertenece al juego
        player = self._get_player(request.owner, game_id)
        
        # 3. Validar que es el turno del jugador
        self._validate_player_turn(game, player)
        
        # 4. Obtener el turno actual
        current_turn = self._get_current_turn(game_id, player.id)
        
        # 5. Validar que las cartas existen y están en la mano del jugador
        cards = self._validate_cards_in_hand(request.cards, player.id, game_id)
        
        # 6. Validar que el set es válido según el tipo
        self._validate_set_combination(cards, request.setType, request.hasWildcard)
        
        # 7. Obtener la siguiente posición de set disponible para este jugador
        next_position = self._get_next_set_position(game_id, player.id)
        
        # 8. Actualizar las cartas a DETECTIVE_SET (moverlas de HAND)
        self._move_cards_to_detective_set(cards, next_position)
        
        # 9. Crear la acción padre en ActionsPerTurn
        action = self._create_detective_action(
            game_id=game_id,
            turn_id=current_turn.id,
            player_id=player.id,
            set_type=request.setType
        )
        
        # 10. Determinar la siguiente acción según el tipo de set
        next_action = self._determine_next_action(
            set_type=request.setType,
            has_wildcard=request.hasWildcard,
            game_id=game_id,
            owner_id=player.id
        )
        
        # 11. Commit de la transacción
        self.db.commit()
        
        return action.id, next_action
    
    def _get_game(self, game_id: int) -> Game:
        """Obtiene el juego o lanza 404"""
        game = crud.get_game_by_id(self.db, game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        return game
    
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
    
    def _validate_player_turn(self, game: Game, player: Player):
        """Valida que es el turno del jugador"""
        if game.player_turn_id != player.id:
            raise HTTPException(
                status_code=403, 
                detail="Not your turn"
            )
    
    def _get_current_turn(self, game_id: int, player_id: int) -> Turn:
        """Obtiene el turno actual del jugador"""
        turn = crud.get_active_turn_for_player(self.db, game_id, player_id)
        
        if not turn:
            raise HTTPException(
                status_code=404, 
                detail="No active turn found for player"
            )
        
        return turn
    
    def _validate_cards_in_hand(
        self, 
        card_ids: List[int], 
        player_id: int, 
        game_id: int
    ) -> List[CardsXGame]:
        """Valida que todas las cartas existen y están en la mano del jugador"""
        cards = crud.get_cards_in_hand_by_ids(self.db, card_ids, player_id, game_id)
        
        if len(cards) != len(card_ids):
            raise HTTPException(
                status_code=400, 
                detail="Some cards are not in player's hand or do not exist"
            )
        
        return cards
    
    def _validate_set_combination(
        self, 
        cards: List[CardsXGame], 
        set_type: SetType,
        has_wildcard: bool
    ):
        """Valida que las cartas forman un set válido según el tipo"""
        # Verificar cantidad mínima
        min_cards = SET_MIN_CARDS[set_type]
        if len(cards) < min_cards:
            raise HTTPException(
                status_code=400,
                detail=f"{set_type.value} set requires at least {min_cards} cards"
            )
        
        # Obtener los id_card de las cartas
        card_types = [card.id_card for card in cards]
        
        # Contar comodines
        wildcard_count = card_types.count(self.HARLEY_QUIN_CARD_ID)
        
        # Validar que hasWildcard coincide con la realidad
        if has_wildcard and wildcard_count == 0:
            raise HTTPException(
                status_code=400,
                detail="hasWildcard is true but no Harley Quin card found"
            )
        
        if not has_wildcard and wildcard_count > 0:
            raise HTTPException(
                status_code=400,
                detail="Harley Quin found but hasWildcard is false"
            )
        
        # Validación específica por tipo de set
        if set_type == SetType.BERESFORD:
            self._validate_beresford_set(card_types, wildcard_count)
        else:
            self._validate_regular_set(card_types, set_type, wildcard_count)
    
    def _validate_beresford_set(self, card_types: List[int], wildcard_count: int):
        """Valida set de Hermanos Beresford (caso especial)"""
        non_wildcard = [c for c in card_types if c != self.HARLEY_QUIN_CARD_ID]
        
        # Debe tener al menos 2 cartas totales
        if len(card_types) < 2:
            raise HTTPException(
                status_code=400,
                detail="Beresford set requires at least 2 cards"
            )
        
        # Casos válidos:
        # 1. 2 iguales (Tommy + Tommy o Tuppence + Tuppence)
        # 2. Tommy + Tuppence
        # 3. 1 hermano + comodín
        
        tommy_count = non_wildcard.count(self.TOMMY_BERESFORD_CARD_ID)
        tuppence_count = non_wildcard.count(self.TUPPENCE_BERESFORD_CARD_ID)
        
        valid = False
        
        # Caso 1: 2 o más del mismo hermano
        if tommy_count >= 2 or tuppence_count >= 2:
            valid = True
        
        # Caso 2: Tommy + Tuppence
        if tommy_count >= 1 and tuppence_count >= 1:
            valid = True
        
        # Caso 3: 1 hermano + comodín
        if (tommy_count == 1 or tuppence_count == 1) and wildcard_count >= 1:
            valid = True
        
        if not valid:
            raise HTTPException(
                status_code=400,
                detail="Invalid Beresford set combination"
            )
    
    def _validate_regular_set(
        self, 
        card_types: List[int], 
        set_type: SetType, 
        wildcard_count: int
    ):
        """Valida sets regulares (Poirot, Marple, Satterthwaite, Pyne, Eileen)"""
        expected_card_id = self.SET_CARD_IDS[set_type]
        
        # Contar cartas del tipo esperado (excluyendo comodines)
        matching_cards = [c for c in card_types if c == expected_card_id]
        
        # Total de cartas válidas = cartas correctas + comodines
        total_valid = len(matching_cards) + wildcard_count
        min_required = SET_MIN_CARDS[set_type]
        
        # Debe tener al menos 1 carta del tipo correcto (no solo comodines)
        if len(matching_cards) < 1:
            raise HTTPException(
                status_code=400,
                detail=f"Set must contain at least 1 {set_type.value} card"
            )
        
        # El total debe cumplir el mínimo
        if total_valid < min_required:
            raise HTTPException(
                status_code=400,
                detail=f"{set_type.value} set requires at least {min_required} valid cards"
            )
        
        # No debe haber cartas de otros tipos
        invalid_cards = [c for c in card_types 
                        if c != expected_card_id and c != self.HARLEY_QUIN_CARD_ID]
        if invalid_cards:
            raise HTTPException(
                status_code=400,
                detail=f"Set contains invalid cards for {set_type.value}"
            )
    
    def _get_next_set_position(self, game_id: int, player_id: int) -> int:
        """Obtiene la siguiente posición disponible para un nuevo set del jugador"""
        max_position = crud.get_max_position_for_player_by_state(
            self.db, game_id, player_id, CardState.DETECTIVE_SET
        )
        return max_position + 1
    
    def _move_cards_to_detective_set(self, cards: List[CardsXGame], position: int):
        """Mueve las cartas de HAND a DETECTIVE_SET con la misma position"""
        crud.update_cards_state(self.db, cards, CardState.DETECTIVE_SET, position, hidden=False)
    
    def _create_detective_action(
        self,
        game_id: int,
        turn_id: int,
        player_id: int,
        set_type: SetType
    ) -> ActionsPerTurn:
        """Crea la acción padre en ActionsPerTurn con estado PENDING"""
        action_data = {
            "id_game": game_id,
            "turn_id": turn_id,
            "player_id": player_id,
            "action_name": SET_ACTION_NAMES[set_type],
            "action_type": ActionType.DETECTIVE_SET,
            "result": ActionResult.PENDING,
            "parent_action_id": None,
            "triggered_by_action_id": None
        }
        
        return crud.create_action(self.db, action_data)
    
    def _determine_next_action(
        self,
        set_type: SetType,
        has_wildcard: bool,
        game_id: int,
        owner_id: int
    ) -> NextAction:
        """Determina cuál es la siguiente acción requerida según el tipo de set"""
        # Obtener jugadores permitidos (todos excepto el owner)
        allowed_players = self._get_allowed_players(game_id, owner_id)
        
        metadata = NextActionMetadata(hasWildcard=has_wildcard)
        
        # Poirot y Marple: el activo elige jugador Y secreto (cualquiera, oculto o revelado)
        if set_type in [SetType.POIROT, SetType.MARPLE]:
            secrets_info = self._get_secrets_info(game_id, allowed_players, only_revealed=False)
            metadata.secretsPool = secrets_info
            return NextAction(
                type=NextActionType.SELECT_PLAYER_AND_SECRET,
                allowedPlayers=allowed_players,
                metadata=metadata
            )
        
        # Pyne: el activo elige jugador Y secreto REVELADO solamente
        if set_type == SetType.PYNE:
            secrets_info = self._get_secrets_info(game_id, allowed_players, only_revealed=True)
            metadata.secretsPool = secrets_info
            return NextAction(
                type=NextActionType.SELECT_PLAYER_AND_SECRET,
                allowedPlayers=allowed_players,
                metadata=metadata
            )
        
        # Satterthwaite, Beresford, Eileen Brent: el activo elige jugador
        # (luego el oponente elegirá su propio secreto en el otro endpoint)
        if set_type in [SetType.SATTERTHWAITE, SetType.BERESFORD, SetType.EILEENBRENT]:
            return NextAction(
                type=NextActionType.SELECT_PLAYER,
                allowedPlayers=allowed_players,
                metadata=metadata
            )
        
        # Por defecto (no debería llegar aquí)
        raise HTTPException(
            status_code=500,
            detail=f"Unknown set type: {set_type}"
        )
    
    def _get_allowed_players(self, game_id: int, exclude_player_id: int) -> List[int]:
        """
        Obtiene la lista de jugadores permitidos como objetivo.
        Excluye al owner y a jugadores en desgracia social.
        """
        return crud.get_players_not_in_disgrace(self.db, game_id, exclude_player_id)
    
    def _get_secrets_info(self, game_id: int, allowed_players: List[int], only_revealed: bool = False) -> List[SecretInfo]:
        """
        Obtiene información de los secretos disponibles para robar.
        
        Args:
            game_id: ID del juego
            allowed_players: Lista de IDs de jugadores de los que se pueden robar secretos
            only_revealed: Si True, solo incluye secretos revelados (hidden=False)
        
        Returns:
            Lista de SecretInfo con position, playerId, hidden y cardId (si está revelado)
        """
        secrets = []
        
        for player_id in allowed_players:
            # Obtener secretos del jugador
            query = self.db.query(CardsXGame).filter(
                CardsXGame.id_game == game_id,
                CardsXGame.player_id == player_id,
                CardsXGame.is_in == CardState.SECRET_SET
            ).order_by(CardsXGame.position)
            
            if only_revealed:
                query = query.filter(CardsXGame.hidden == False)
            
            player_secrets = query.all()
            
            for secret_card in player_secrets:
                card_id = None
                if not secret_card.hidden:
                    # Si está revelado, incluir el ID de la carta
                    card_id = secret_card.id_card
                
                secrets.append(SecretInfo(
                    playerId=player_id,
                    position=secret_card.position,
                    hidden=secret_card.hidden,
                    cardId=card_id
                ))
        
        return secrets

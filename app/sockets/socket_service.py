# app/sockets/socket_service.py
from .socket_manager import get_ws_manager
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketService:
    """Interface publica para que otros servicios usen WebSocket"""
    def __init__(self):
        self.ws_manager = get_ws_manager()

    # --------------
    # | GAME STATE |
    # --------------
    
    async def notificar_estado_publico(
        self,
        room_id: int,
        game_state: Dict[str, Any]
    ):
        """
        Notify public game state to all players in room
        
        Args:
            room_id: Room ID
            game_state: Dict containing:
                - game_id: int
                - status: str (WAITING, INGAME, FINISH)
                - turno_actual: int (player_id)
                - jugadores: List[Dict] (player info)
                - mazos: Dict (deck, discard, draft counts/data)
        """
        logger.info(f"🔵 Notifying public state to room {room_id}")
        
        mensaje_publico = {
            "type": "game_state_public",
            "room_id": room_id,
            "game_id": game_state.get("game_id"),
            "status": game_state.get("status", "WAITING"),
            "turno_actual": game_state.get("turno_actual"),
            "jugadores": game_state.get("jugadores", []),
            "mazos": game_state.get("mazos", {}),
            "sets": game_state.get("sets", []),
            "secretsFromAllPlayers": game_state.get("secretsFromAllPlayers", []),
            "timestamp": datetime.now().isoformat()
        }
        
        await self.ws_manager.emit_to_room(room_id, "game_state_public", mensaje_publico)
        logger.info(f"✅ Emitted game_state_public to room {room_id}")
    
    async def notificar_estados_privados(
        self,
        room_id: int,
        estados_privados: Dict[int, Dict[str, Any]]
    ):
        """
        Notify private game state to each player individually
        
        Args:
            room_id: Room ID
            estados_privados: Dict mapping player_id to their private data:
                {
                    player_id: {
                        "mano": List[Dict],
                        "secretos": List[Dict]
                    }
                }
        """
        logger.info(f"🟢 Notifying private states to room {room_id}")
        sids = self.ws_manager.get_sids_in_game(room_id)
        
        if not sids:
            logger.warning(f"Room {room_id} has no connected players")
            return
          
        for sid in sids:
            session = self.ws_manager.get_user_session(sid)
            if not session:
                continue
            
            user_id = session["user_id"]
            private_data = estados_privados.get(user_id, {})
            
            mensaje_privado = {
                "type": "game_state_private",
                "user_id": user_id,
                "mano": private_data.get("mano", []),
                "secretos": private_data.get("secretos", []),
                "timestamp": datetime.now().isoformat()
            }
            
            await self.ws_manager.emit_to_sid(sid, "game_state_private", mensaje_privado)
            logger.info(f"✅ Emitted game_state_private to user {user_id}")
    
    async def notificar_fin_partida(
        self,
        room_id: int,
        winners: List[Dict[str, Any]],
        reason: str
    ):
        """
        Notify game ended to all players individually
        
        Args:
            room_id: Room ID
            winners: List of winner dicts:
                [{"player_id": 1, "name": "Player 1", ...}]
            reason: String explaining why game ended
        """
        logger.info(f"🏁 Notifying game ended to room {room_id}")
        sids = self.ws_manager.get_sids_in_game(room_id)
        
        if not sids:
            logger.warning(f"Room {room_id} has no connected players")
            return
        
        for sid in sids:
            session = self.ws_manager.get_user_session(sid)
            if not session:
                continue
            
            user_id = session["user_id"]
            is_winner = any(w.get("player_id") == user_id for w in winners)
            
            resultado = {
                "type": "game_ended",
                "user_id": user_id,
                "ganaste": is_winner,
                "winners": winners,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.ws_manager.emit_to_sid(sid, "game_ended", resultado)
            print(f"✅ Se emitio el fin de partida")
            logger.info(f"✅ Emitted game_ended to user {user_id} (winner: {is_winner})")
    
    # --------------------------------------------
    # | Metodo Anterior - backward compatibility |
    # --------------------------------------------
    
    async def notificar_estado_partida(
        self,
        room_id: int,
        jugador_que_actuo: Optional[int] = None,
        game_state: Optional[Dict] = None,
        partida_finalizada: bool = False,
    ):
        """
        LEGACY METHOD - Combines all notifications
        Kept for backward compatibility, but prefer using individual methods
        
        This calls the three refactored methods internally
        """
        logger.info(f"🎮 Notifying game state to room {room_id} (legacy method)")
        
        if not game_state:
            logger.warning(f"No game_state provided to notificar_estado_partida")
            return
        
        # 1. Public state
        await self.notificar_estado_publico(room_id, game_state)
        
        # 2. Private states
        if game_state.get("estados_privados"):
            await self.notificar_estados_privados(
                room_id, 
                game_state["estados_privados"]
            )
        
        # 3. Game ended (if applicable)
        if partida_finalizada:
            await self.notificar_fin_partida(
                room_id=room_id,
                winners=game_state.get("winners", []),
                reason=game_state.get("finish_reason", "Game completed")
            )

    # ---------------------
    # | DETECTIVE ACTIONS |
    # ---------------------
    
    async def notificar_detective_action_started(
        self,
        room_id: int,
        player_id: int,
        set_type: str
    ):
        """Notify all players that a detective action has started"""
        mensaje = {
            "type": "detective_action_started",
            "player_id": player_id,
            "set_type": set_type,
            "message": f"Player {player_id} is playing {set_type}",
            "timestamp": datetime.now().isoformat()
        }
        await self.ws_manager.emit_to_room(room_id, "detective_action_started", mensaje)
        logger.info(f"✅ Emitted detective_action_started to room {room_id}")
    
    async def notificar_card_trade_select_own_card(
        self,
        room_id: int,
        action_id: int,
        requester_id: int,
        requester_name: str,
        target_id: int
    ):
        """
        Notifica a P2 (target) que debe seleccionar su carta para el intercambio.
        
        Args:
            room_id: ID de la sala
            action_id: ID de la acción de Card Trade
            requester_id: ID del jugador que inició el trade (P1)
            requester_name: Nombre del jugador que inició el trade
            target_id: ID del jugador que debe seleccionar (P2)
        """
        event_data = {
            "action_id": action_id,
            "requester_id": requester_id,
            "requester_name": requester_name,
            "target_id": target_id,
            "message": f"{requester_name} quiere intercambiar una carta contigo"
        }
        
        await self.ws_manager.emit_to_room(
            room_id, 
            "card_trade_select_own_card", 
            event_data
        )
        
        logger.info(
            f"[WS] card_trade_select_own_card emitido a room {room_id}. "
            f"Target: {target_id}, Requester: {requester_id}, Action: {action_id}"
        )


    async def notificar_card_trade_complete(
        self,
        room_id: int,
        player1_id: int,
        player1_name: str,
        player2_id: int,
        player2_name: str,
        message: str
    ):
        """
        Notifica a todos los jugadores que el Card Trade se completó exitosamente.
        
        Args:
            room_id: ID de la sala
            player1_id: ID del jugador que inició el trade
            player1_name: Nombre del jugador que inició el trade
            player2_id: ID del jugador objetivo
            player2_name: Nombre del jugador objetivo
            message: Mensaje descriptivo del intercambio
        """
        event_data = {
            "player1_id": player1_id,
            "player1_name": player1_name,
            "player2_id": player2_id,
            "player2_name": player2_name,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.ws_manager.emit_to_room(
            room_id, 
            "card_trade_complete", 
            event_data
        )
        
        logger.info(
            f"[WS] card_trade_complete emitido a room {room_id}. "
            f"P1: {player1_id}, P2: {player2_id}"
        )
            
    
    async def notificar_detective_target_selected(
        self,
        room_id: int,
        player_id: int,
        target_player_id: int,
        set_type: str
    ):
        """Notify all players that a target has been selected"""
        mensaje = {
            "type": "detective_target_selected",
            "player_id": player_id,
            "target_player_id": target_player_id,
            "set_type": set_type,
            "message": f"Player {target_player_id} must choose a secret",
            "timestamp": datetime.now().isoformat()
        }
        await self.ws_manager.emit_to_room(room_id, "detective_target_selected", mensaje)
        logger.info(f"✅ Emitted detective_target_selected to room {room_id}")
    
    async def notificar_detective_action_request(
        self,
        room_id: int,
        target_player_id: int,
        action_id: str,
        requester_id: int,
        set_type: str
    ):
        """Notify target player to choose their secret (private message)"""
        sids = self.ws_manager.get_sids_in_game(room_id)
        
        for sid in sids:
            session = self.ws_manager.get_user_session(sid)
            if session and session["user_id"] == target_player_id:
                mensaje = {
                    "type": "select_own_secret",
                    "action_id": action_id,
                    "requester_id": requester_id,
                    "set_type": set_type,
                    "timestamp": datetime.now().isoformat()
                }
                await self.ws_manager.emit_to_sid(sid, "select_own_secret", mensaje)
                logger.info(f"✅ Notified player {target_player_id} to choose secret")
                break
    
    async def notificar_detective_action_complete(
        self,
        room_id: int,
        action_type: str,
        player_id: int,
        target_player_id: int,
        secret_id: Optional[int] = None,
        action: str = "revealed",  # "revealed" or "hidden"
        wildcard_used: bool = False,
        secret_data: Optional[dict] = None,
        message: Optional[str] = None
    ):
        """Notify all players that detective action is complete"""
        mensaje = {
            "type": "detective_action_complete",
            "action_type": action_type,
            "player_id": player_id,
            "target_player_id": target_player_id,
            "secret_id": secret_id,
            "action": action,
            "wildcard_used": wildcard_used,
            "secret_data": secret_data,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        await self.ws_manager.emit_to_room(room_id, "detective_action_complete", mensaje)
        logger.info(f"✅ Broadcast detective action complete to room {room_id}")
    
    # ---------------
    # | EVENT CARDS | 
    # ---------------
    
    async def notificar_event_action_started(
        self,
        room_id: int,
        player_id: int,
        event_type: str,
        card_name: str,
        step: str = "started"
    ):
        """Notify all players that an event card action has started"""
        mensaje = {
            "type": "event_action_started",
            "player_id": player_id,
            "event_type": event_type,
            "card_name": card_name,
            "step": step,
            "message": f"Player {player_id} is playing {card_name}",
            "timestamp": datetime.now().isoformat()
        }
        await self.ws_manager.emit_to_room(room_id, "event_action_started", mensaje)
        logger.info(f"✅ Emitted event_action_started to room {room_id}")
    
    async def notificar_event_step_update(
        self,
        room_id: int,
        player_id: int,
        event_type: str,
        step: str,
        message: str,
        data: Optional[Dict] = None
    ):
        """Notify all players of an event action step update (transparency)"""
        mensaje = {
            "type": "event_step_update",
            "player_id": player_id,
            "event_type": event_type,
            "step": step,
            "message": message,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        }
        await self.ws_manager.emit_to_room(room_id, "event_step_update", mensaje)
        logger.info(f"✅ Emitted event_step_update to room {room_id}: {step}")
    
    async def notificar_event_action_complete(
        self,
        room_id: int,
        player_id: int,
        event_type: str
    ):
        """Notify all players that event action is complete"""
        mensaje = {
            "type": "event_action_complete",
            "player_id": player_id,
            "event_type": event_type,
            "timestamp": datetime.now().isoformat()
        }
        await self.ws_manager.emit_to_room(room_id, "event_action_complete", mensaje)
        logger.info(f"✅ Emitted event_action_complete to room {room_id}")

    # ---------------------
    # | DEAD CARD FOLLY   |
    # ---------------------
    
    async def notificar_dead_card_folly_select_card(
        self,
        room_id: int,
        action_id: int,
        direction: str,
        player_id: int,
        player_name: str
    ):
        """
        Notifica a todos los jugadores que deben seleccionar una carta para intercambiar.
        
        Args:
            room_id: ID del room
            action_id: ID de la acción padre (EVENT_CARD)
            direction: Dirección del intercambio ("LEFT" o "RIGHT")
            player_id: ID del jugador que jugó Dead Card Folly
            player_name: Nombre del jugador que jugó la carta
        """
        # Traducir dirección
        direccion_es = "izquierda" if direction == "LEFT" else "derecha"
        
        mensaje = {
            "type": "dead_card_folly_select_card",
            "action_id": action_id,
            "direction": direction,
            "player_id": player_id,
            "player_name": player_name,
            "message": f"Jugador {player_name} jugó Dead Card Folly, todos los jugadores tendrán que seleccionar una carta para pasarle a su jugador de la {direccion_es}",
            "timestamp": datetime.now().isoformat()
        }
        
        await self.ws_manager.emit_to_room(room_id, "dead_card_folly_select_card", mensaje)
        logger.info(
            f"🔄 Emitted dead_card_folly_select_card to room {room_id}: "
            f"Action {action_id}, direction={direction}"
        )
    
    async def notificar_dead_card_folly_complete(
        self,
        room_id: int,
        action_id: int,
        direction: str,
        players_count: int
    ):
        """
        Notifica a todos los jugadores que el intercambio se completó.
        
        Args:
            room_id: ID del room
            action_id: ID de la acción padre (EVENT_CARD)
            direction: Dirección del intercambio ("LEFT" o "RIGHT")
            players_count: Número de jugadores que participaron
        """
        mensaje = {
            "type": "dead_card_folly_complete",
            "action_id": action_id,
            "direction": direction,
            "players_count": players_count,
            "message": "Acción de Dead Card Folly terminada",
            "timestamp": datetime.now().isoformat()
        }
        
        await self.ws_manager.emit_to_room(room_id, "dead_card_folly_complete", mensaje)
        logger.info(
            f"✅ Emitted dead_card_folly_complete to room {room_id}: "
            f"Action {action_id}, {players_count} players"
        )

    # ----------------
    # | DISCARD-DRAW |
    # ----------------

    async def notificar_player_must_draw(
        self,
        room_id: int,
        player_id: int,
        cards_to_draw: int
    ):
        """Notify all players that someone finished discarding and must draw"""
        mensaje = {
            "type": "player_must_draw",
            "player_id": player_id,
            "cards_to_draw": cards_to_draw,
            "message": f"Player {player_id} must draw {cards_to_draw} cards",
            "timestamp": datetime.now().isoformat()
        }
        await self.ws_manager.emit_to_room(room_id, "player_must_draw", mensaje)
        logger.info(f"✅ Emitted player_must_draw to room {room_id}")
        print(f"✅ Emitted player_must_draw to room {room_id}")


    async def notificar_card_drawn_simple(
        self,
        room_id: int,
        player_id: int,
        drawn_from: str,  # "deck" or "draft"
        cards_remaining: int
    ):
        """Notify all players that a card was drawn"""
        mensaje = {
            "type": "card_drawn_simple",
            "player_id": player_id,
            "drawn_from": drawn_from,
            "cards_remaining": cards_remaining,
            "message": f"Player {player_id} drew from {drawn_from} ({cards_remaining} more to draw)",
            "timestamp": datetime.now().isoformat()
        }
        await self.ws_manager.emit_to_room(room_id, "card_drawn_simple", mensaje)
        logger.info(f"✅ Emitted card_drawn_simple to room {room_id}")

    async def notificar_turn_finished(
        self,
        room_id: int,
        player_id: int,
    ):
        """Notify all players that a turn has been finished"""
        mensaje = {
            "type": "turn_finished",
            "player_id": player_id,
            "message": f"Player {player_id} finished their turn.",
            "timestamp": datetime.now().isoformat()
        }
        await self.ws_manager.emit_to_room(room_id, "turn_finished", mensaje)
        logger.info(f"✅ Emitted turn_finished to room {room_id}: Player {player_id}")

    # ----------------------
    # | LOBBY - LEAVE GAME |
    # ----------------------
    
    async def notificar_game_cancelled(
        self,
        room_id: int,
        timestamp: str
    ):
        """
        Notificar a todos los jugadores que la partida fue cancelada
        Todos los jugadores deben ser redirigidos a /lobby
        """
        mensaje = {
            "type": "game_cancelled",
            "room_id": room_id,
            "timestamp": timestamp
        }
        await self.ws_manager.emit_to_room(room_id, "game_cancelled", mensaje)
        logger.info(f"Emitted game_cancelled to room {room_id}")
    
    async def notificar_player_left(
        self,
        room_id: int,
        player_id: int,
        players_count: int,
        players: list,
        timestamp: str
    ):
        """
        Notificar a todos los jugadores que alguien abandono la sala
        Actualizar la lista de jugadores en la sala
        """
        mensaje = {
            "type": "player_left",
            "player_id": player_id,
            "players_count": players_count,
            "players": players,
            "timestamp": timestamp
        }
        await self.ws_manager.emit_to_room(room_id, "player_left", mensaje)
        logger.info(f"Emitted player_left to room {room_id}: player {player_id} left")

    # ---------------------
    # | SOCIAL DISGRACE   |
    # ---------------------
    
    async def notificar_social_disgrace_update(
        self,
        room_id: int,
        game_id: int,
        players_in_disgrace: List[Dict[str, Any]],
        change_info: Optional[Dict[str, Any]] = None
    ):
        """
        Notifica a todos los jugadores sobre cambios en desgracia social.
        
        Args:
            room_id: ID del room
            game_id: ID del juego
            players_in_disgrace: Lista de jugadores actualmente en desgracia social
            change_info: Información del cambio (quien entró/salió)
        """
        # Preparar el mensaje
        message = None
        if change_info:
            action = change_info.get("action")
            player_name = change_info.get("player_name")
            if action == "entered":
                message = f"{player_name} ha entrado en desgracia social"
            elif action == "exited":
                message = f"{player_name} ha salido de desgracia social"
        
        mensaje = {
            "type": "social_disgrace_update",
            "game_id": game_id,
            "players_in_disgrace": players_in_disgrace,
            "message": message,
            "change": change_info,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.ws_manager.emit_to_room(room_id, "social_disgrace_update", mensaje)
        print(f"'social_disgrace_update' emitido a room {room_id}")

    # ==================
    # | NOT SO FAST    |
    # ==================
    
    async def notificar_valid_action(
        self,
        room_id: int,
        action_id: int,
        player_id: int,
        action_type: str,
        action_name: str,
        cancellable: bool
    ):
        """
        Notifica que una acción es válida y está en proceso.
        
        Args:
            room_id: ID del room
            action_id: ID de la acción (intención)
            player_id: ID del jugador que inicia la acción
            action_type: Tipo de acción (EVENT_CARD, DETECTIVE_SET, etc)
            action_name: Nombre de la acción
            cancellable: Si la acción puede ser contrarrestada con NSF
        """
        mensaje = {
            "type": "valid_action",
            "action_id": action_id,
            "player_id": player_id,
            "action_type": action_type,
            "action_name": action_name,
            "cancellable": cancellable,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.ws_manager.emit_to_room(room_id, "valid_action", mensaje)
        logger.info(
            f"✅ Emitted valid_action to room {room_id}: "
            f"Player {player_id} - {action_name} (cancellable={cancellable})"
        )
    
    async def notificar_nsf_counter_start(
        self,
        room_id: int,
        action_id: int,
        nsf_action_id: int,
        player_id: int,
        action_type: str,
        action_name: str,
        time_remaining: int
    ):
        """
        Notifica el inicio de la ventana NSF.
        
        Args:
            room_id: ID del room
            action_id: ID de la acción original (intención)
            nsf_action_id: ID de la acción NSF
            player_id: ID del jugador que inició la acción
            action_type: Tipo de acción
            action_name: Nombre de la acción
            time_remaining: Tiempo en segundos de la ventana NSF
        """
        mensaje = {
            "type": "nsf_counter_start",
            "action_id": action_id,
            "nsf_action_id": nsf_action_id,
            "player_id": player_id,
            "action_type": action_type,
            "action_name": action_name,
            "time_remaining": time_remaining,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.ws_manager.emit_to_room(room_id, "nsf_counter_start", mensaje)
        logger.info(
            f"⏱️  Emitted nsf_counter_start to room {room_id}: "
            f"Action {action_id} - {time_remaining}s window"
        )
    
    async def notificar_nsf_counter_tick(
        self,
        room_id: int,
        action_id: int,
        remaining_time: float,
        elapsed_time: float
    ):
        """
        Notifica actualización del timer NSF (cada segundo).
        
        Args:
            room_id: ID del room
            action_id: ID de la acción NSF
            remaining_time: Segundos restantes
            elapsed_time: Segundos transcurridos
        """
        mensaje = {
            "type": "nsf_counter_tick",
            "action_id": action_id,
            "remaining_time": remaining_time,
            "elapsed_time": elapsed_time,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.ws_manager.emit_to_room(room_id, "nsf_counter_tick", mensaje)
        # Log temporal para debugging
        logger.info(
            f"⏱️  Emitted nsf_counter_tick to room {room_id}: "
            f"Action {action_id} - {remaining_time}s remaining, {elapsed_time}s elapsed"
        )
    
    async def notificar_nsf_played(
        self,
        room_id: int,
        action_id: int,
        nsf_action_id: int,
        player_id: int,
        card_id: int,
        player_name: str,
    ):
        """
        Notifica que un jugador jugó una carta NSF.
        
        Args:
            room_id: ID del room
            action_id: ID de la acción NSF principal (YYY)
            nsf_action_id: ID de esta jugada NSF específica (ZZZ)
            player_id: ID del jugador que jugó NSF
            card_id: ID de la carta NSF jugada (cardsXgame.id)
            player_name: Nombre del jugador para el mensaje
        """
        mensaje = {
            "type": "nsf_played",
            "action_id": action_id,
            "nsf_action_id": nsf_action_id,
            "player_id": player_id,
            "card_id": card_id,
            "message": f"Player {player_name} jugó Not So Fast",
            "timestamp": datetime.now().isoformat()
        }
        
        await self.ws_manager.emit_to_room(room_id, "nsf_played", mensaje)
        logger.info(
            f"🛡️  Emitted nsf_played to room {room_id}: "
            f"Player {player_name} (ID: {player_id}) played NSF"
        )
    
    async def notificar_nsf_counter_complete(
        self,
        room_id: int,
        action_id: int,
        final_result: str,
        message: str
    ):
        """
        Notifica el fin de la ventana NSF con el resultado final.
        
        Args:
            room_id: ID del room
            action_id: ID de la acción original
            final_result: Resultado final ("cancelled" o "continue")
            message: Mensaje descriptivo del resultado
        """
        mensaje = {
            "type": "nsf_counter_complete",
            "action_id": action_id,
            "final_result": final_result,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.ws_manager.emit_to_room(room_id, "nsf_counter_complete", mensaje)
        logger.info(
            f"🏁 Emitted nsf_counter_complete to room {room_id}: "
            f"Action {action_id} result={final_result} - {message}"
        )
    
    async def notificar_accion_cancelada_ejecutada(
        self,
        room_id: int,
        action_id: int,
        player_id: int,
        message: str
    ):
        """
        Notifica que una acción cancelada fue ejecutada sin efectos.
        
        Args:
            room_id: ID del room
            action_id: ID de la acción original (XXX)
            player_id: ID del jugador que ejecutó la acción
            message: Mensaje descriptivo de lo que ocurrió
        """
        mensaje = {
            "type": "cancelled_action_executed",
            "action_id": action_id,
            "player_id": player_id,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.ws_manager.emit_to_room(room_id, "cancelled_action_executed", mensaje)
        logger.info(
            f"🚫 Emitted cancelled_action_executed to room {room_id}: "
            f"Action {action_id} - {message}"
        )

_websocket_service = None

def get_websocket_service() -> WebSocketService:
    global _websocket_service
    if _websocket_service is None:
        _websocket_service = WebSocketService()
    return _websocket_service

_websocket_service = None

def get_websocket_service() -> WebSocketService:
    global _websocket_service
    if _websocket_service is None:
        _websocket_service = WebSocketService()
    return _websocket_service

_websocket_service = None

def get_websocket_service() -> WebSocketService:
    global _websocket_service
    if _websocket_service is None:
        _websocket_service = WebSocketService()
    return _websocket_service

_websocket_service = None

def get_websocket_service() -> WebSocketService:
    global _websocket_service
    if _websocket_service is None:
        _websocket_service = WebSocketService()
    return _websocket_service
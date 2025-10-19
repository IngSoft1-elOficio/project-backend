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
        wildcard_used: bool = False
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

_websocket_service = None

def get_websocket_service() -> WebSocketService:
    global _websocket_service
    if _websocket_service is None:
        _websocket_service = WebSocketService()
    return _websocket_service
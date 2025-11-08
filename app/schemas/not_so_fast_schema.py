"""
Schemas para la funcionalidad Not So Fast (NSF)
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime


# ========================
# HELPER SCHEMAS
# ========================

class AdditionalData(BaseModel):
    """
    Datos adicionales para la acción.
    """
    actionType: Literal["EVENT", "CREATE_SET", "ADD_TO_SET"] = Field(..., description="Tipo de acción a realizar")
    setPosition: Optional[int] = Field(default=None, description="Posición del set al que se agrega la carta (obligatorio si actionType=ADD_TO_SET)")
    
    @field_validator('setPosition')
    @classmethod
    def validate_set_position(cls, v, info):
        """Valida que setPosition esté presente cuando actionType=ADD_TO_SET"""
        action_type = info.data.get('actionType')
        if action_type == 'ADD_TO_SET' and v is None:
            raise ValueError('setPosition is required when actionType is ADD_TO_SET')
        return v


# ========================
# REQUEST SCHEMAS
# ========================

class StartActionRequest(BaseModel):
    """
    Request para iniciar una acción que puede ser contrarrestada con NSF.
    
    El frontend envía:
    - playerId: quien inicia la acción
    - cardIds: las cartas involucradas en la acción
    - additionalData: objeto con actionType y setPosition (opcional)
    """
    playerId: int = Field(..., description="ID del jugador que inicia la acción")
    cardIds: List[int] = Field(..., description="Lista de IDs de cartas (cardsXgame.id) jugadas en la acción")
    additionalData: AdditionalData = Field(..., description="Datos adicionales de la acción")

    class Config:
        json_schema_extra = {
            "example_event": {
                "playerId": 1,
                "cardIds": [15],
                "additionalData": {
                    "actionType": "EVENT",
                    "setPosition": None
                }
            },
            "example_create_set": {
                "playerId": 1,
                "cardIds": [5, 6],
                "additionalData": {
                    "actionType": "CREATE_SET",
                    "setPosition": None
                }
            },
            "example_add_to_set": {
                "playerId": 1,
                "cardIds": [7],
                "additionalData": {
                    "actionType": "ADD_TO_SET",
                    "setPosition": 2
                }
            }
        }


# ========================
# RESPONSE SCHEMAS
# ========================

class PlayNSFRequest(BaseModel):
    """
    Request para jugar una carta Not So Fast.
    
    El frontend envía:
    - actionId: ID de la acción original que está siendo contrarrestada
    - playerId: ID del jugador que juega la NSF
    - cardId: ID de la carta NSF en cardsXgame.id
    """
    actionId: int = Field(..., description="ID de la acción original siendo contrarrestada")
    playerId: int = Field(..., description="ID del jugador que juega NSF")
    cardId: int = Field(..., description="ID de la carta NSF (cardsXgame.id)")

    class Config:
        json_schema_extra = {
            "example": {
                "actionId": 123,
                "playerId": 2,
                "cardId": 45
            }
        }


class StartActionResponse(BaseModel):
    """
    Response del endpoint /start-action.
    
    Indica si la acción es cancelable y proporciona los IDs necesarios.
    """
    actionId: int = Field(..., description="ID de la acción de intención")
    actionNSFId: Optional[int] = Field(default=None, description="ID de la acción NSF si es cancelable")
    cancellable: bool = Field(..., description="Indica si la acción puede ser contrarrestada con NSF")
    timeRemaining: Optional[int] = Field(default=None, description="Tiempo en segundos de la ventana NSF (5s si cancellable=true)")

    class Config:
        json_schema_extra = {
            "example_cancellable_false": {
                "actionId": 123,
                "actionNSFId": None,
                "cancellable": False,
                "timeRemaining": None
            },
            "example_cancellable_true": {
                "actionId": 123,
                "actionNSFId": 124,
                "cancellable": True,
                "timeRemaining": 5
            }
        }


class PlayNSFResponse(BaseModel):
    """
    Response del endpoint /instant/not-so-fast.
    
    Confirma que la NSF fue jugada y el timer reiniciado.
    """
    success: bool = Field(..., description="Indica si la NSF fue jugada exitosamente")
    nsfActionId: int = Field(..., description="ID de la acción NSF jugada")
    nsfStartActionId: int = Field(..., description="ID de la acción NSF_START")
    timeRemaining: int = Field(..., description="Tiempo restante en segundos (siempre 5)")
    message: str = Field(..., description="Mensaje descriptivo")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "nsfActionId": 126,
                "nsfStartActionId": 124,
                "timeRemaining": 5,
                "message": "Player John jugó Not So Fast"
            }
        }


# ========================
# INTERNAL/WS EVENT SCHEMAS
# ========================

class NSFCounterStartEvent(BaseModel):
    """
    Evento emitido por WebSocket cuando inicia la ventana NSF.
    
    Event: NSF_COUNTER_START
    """
    event: str = Field(default="NSF_COUNTER_START", description="Nombre del evento")
    data: dict = Field(..., description="Datos del evento")

    class Config:
        json_schema_extra = {
            "example": {
                "event": "NSF_COUNTER_START",
                "data": {
                    "actionId": 123,
                    "nsfActionId": 124,
                    "playerId": 1,
                    "actionType": "EVENT_CARD",
                    "actionName": "Another Victim",
                    "timeRemaining": 5
                }
            }
        }


class NSFCounterTickEvent(BaseModel):
    """
    Evento emitido por WebSocket cada segundo durante la ventana NSF.
    
    Event: NSF_COUNTER_TICK
    """
    event: str = Field(default="NSF_COUNTER_TICK", description="Nombre del evento")
    remaining_time: float = Field(..., description="Segundos restantes en la ventana NSF")
    elapsed_time: float = Field(..., description="Segundos transcurridos desde que empezó el timer")

    class Config:
        json_schema_extra = {
            "example": {
                "event": "NSF_COUNTER_TICK",
                "remaining_time": 3.5,
                "elapsed_time": 1.5
            }
        }


class ValidActionEvent(BaseModel):
    """
    Evento emitido cuando una acción es válida y está en proceso.
    
    Event: VALID_ACTION
    """
    event: str = Field(default="VALID_ACTION", description="Nombre del evento")
    data: dict = Field(..., description="Datos de la acción válida")
    message: str = Field(..., description="Mensaje para el log del juego")

    class Config:
        json_schema_extra = {
            "example": {
                "event": "VALID_ACTION",
                "data": {
                    "actionId": 123,
                    "playerId": 1,
                    "actionType": "EVENT_CARD",
                    "actionName": "Another Victim",
                    "cancellable": True
                },
                "message": "Player 1 plays Another Victim"
            }
        }


# ========================
# CANCEL NSF ENDPOINT
# ========================

class CancelNSFRequest(BaseModel):
    """
    Request para ejecutar una acción cancelada por NSF sin efectos.
    
    Se usa cuando el frontend recibe NSF_COUNTER_COMPLETE con final_result="cancelled"
    y necesita "simular" que la acción se ejecutó pero sin efectos.
    
    Tres casos posibles:
    1. CREATE_SET: Crea el set pero sin ejecutar efecto (excepto Eileen Brent)
    2. EVENT: Mueve carta al discard debajo de las NSF
    3. ADD_TO_SET: Agrega carta al set pero sin efecto
    """
    actionId: int = Field(..., description="ID de la acción original (XXX) que fue cancelada")
    playerId: int = Field(..., description="ID del jugador que inició la acción")
    cardIds: List[int] = Field(..., description="Lista de cardsXgame.id involucrados en la acción")
    additionalData: dict = Field(
        ..., 
        description="Datos adicionales según el tipo de acción (actionType, player_target, setPosition)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "actionId": 123,
                "playerId": 2,
                "cardIds": [45, 46],
                "additionalData": {
                    "actionType": "CREATE_SET",
                    "player_target": None,
                    "setPosition": None
                }
            }
        }


class CancelNSFResponse(BaseModel):
    """
    Response del endpoint /cancel que confirma la ejecución sin efectos.
    """
    success: bool = Field(..., description="Indica si la cancelación fue procesada exitosamente")
    message: str = Field(..., description="Mensaje descriptivo de lo que ocurrió")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Player John jugó Hercule Poirot/Miss Marple pero fue cancelado por NSF - Set created without effect"
            }
        }

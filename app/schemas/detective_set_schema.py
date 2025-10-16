from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from enum import Enum


class SetType(str, Enum):
    """Tipos de sets de detectives permitidos"""
    POIROT = "poirot"
    MARPLE = "marple"
    SATTERTHWAITE = "satterthwaite"
    EILEENBRENT = "eileenbrent"
    BERESFORD = "beresford"
    PYNE = "pyne"


class NextActionType(str, Enum):
    """Tipos de acciones siguientes después de bajar un set"""
    SELECT_PLAYER_AND_SECRET = "selectPlayerAndSecret"  # Poirot/Marple/Pyne
    SELECT_PLAYER = "selectPlayer"  # Satterthwaite/Beresford/Eileen Brent - el activo elige jugador
    WAIT_FOR_OPPONENT = "waitForOpponent"  # Cuando el oponente debe elegir su secreto
    COMPLETE = "complete"  # No requiere más acciones (por ahora no usado)


class SecretInfo(BaseModel):
    """Información de un secreto disponible para ser robado"""
    playerId: int = Field(..., description="ID del jugador dueño del secreto")
    position: int = Field(..., description="Posición del secreto en el set del jugador")
    hidden: bool = Field(..., description="Si el secreto está oculto (True) o revelado (False)")
    cardId: Optional[int] = Field(None, description="ID de la carta si está revelada (para obtener img_src, name, etc.)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "playerId": 2,
                "position": 1,
                "hidden": False,
                "cardId": 15
            }
        }


class NextActionMetadata(BaseModel):
    """Metadatos adicionales para la siguiente acción"""
    hasWildcard: bool = Field(default=False, description="Si el set incluye un comodín")
    secretsPool: Optional[List[SecretInfo]] = Field(
        default=None, 
        description="Lista de secretos disponibles para robar (solo para selectPlayerAndSecret)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "hasWildcard": True,
                "secretsPool": [
                    {
                        "playerId": 2,
                        "position": 1,
                        "hidden": False,
                        "cardName": "The Poisoned Pen"
                    },
                    {
                        "playerId": 3,
                        "position": 2,
                        "hidden": True,
                        "cardName": None
                    }
                ]
            }
        }


class NextAction(BaseModel):
    """Información sobre la siguiente acción requerida"""
    type: NextActionType
    allowedPlayers: List[int] = Field(default_factory=list)
    metadata: Optional[NextActionMetadata] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "selectPlayerAndSecret",
                "allowedPlayers": [1, 2, 3, 4],
                "metadata": {
                    "hasWildcard": False,
                    "secretsPool": None
                }
            }
        }


class PlayDetectiveSetRequest(BaseModel):
    """Request para bajar un set de detectives"""
    owner: int = Field(..., description="ID del jugador que baja el set")
    setType: SetType = Field(..., description="Tipo de set de detective")
    cards: List[int] = Field(..., min_length=1, description="IDs de las cartas del set")
    hasWildcard: bool = Field(default=False, description="Si el set incluye a Harley Quin como comodín")
    
    @validator('cards')
    def validate_cards_not_empty(cls, v):
        if not v:
            raise ValueError("La lista de cartas no puede estar vacía")
        return v
    
    @validator('cards')
    def validate_cards_unique(cls, v):
        if len(v) != len(set(v)):
            raise ValueError("No se pueden repetir IDs de cartas")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "owner": 7,
                "setType": "poirot",
                "cards": [12, 13, 14],
                "hasWildcard": False
            }
        }


class PlayDetectiveSetResponse(BaseModel):
    """Response después de bajar un set de detectives
    
    En este punto solo se validó y se bajó el set.
    La acción queda PENDING esperando el siguiente paso (detective-action).
    """
    success: bool
    actionId: int = Field(..., description="ID de la acción padre creada en ActionsPerTurn con result=PENDING")
    nextAction: NextAction = Field(..., description="Información sobre qué debe hacer el jugador a continuación")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "actionId": 501,
                "nextAction": {
                    "type": "selectPlayerAndSecret",
                    "allowedPlayers": [2, 3, 4],
                    "metadata": {
                        "hasWildcard": False,
                        "secretsPool": None
                    }
                }
            }
        }


# Constantes para validación de sets
SET_MIN_CARDS = {
    SetType.POIROT: 3,
    SetType.MARPLE: 3,
    SetType.SATTERTHWAITE: 2,
    SetType.PYNE: 2,
    SetType.EILEENBRENT: 2,
    SetType.BERESFORD: 2,
}

# Nombres de acción para ActionsPerTurn.action_name
SET_ACTION_NAMES = {
    SetType.POIROT: "play_Poirot_set",
    SetType.MARPLE: "play_Marple_set",
    SetType.SATTERTHWAITE: "play_Satterthwaite_set",
    SetType.PYNE: "play_Pyne_set",
    SetType.EILEENBRENT: "play_EileenBrent_set",
    SetType.BERESFORD: "play_Beresford_set",
}

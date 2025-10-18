# app/schemas/detective_action_schema.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from app.schemas.detective_set_schema import NextAction


class DetectiveActionRequest(BaseModel):
    """Request para ejecutar una acción de detective pendiente"""
    actionId: int = Field(..., description="ID de la acción pendiente en ActionsPerTurn")
    executorId: int = Field(..., description="ID del jugador que ejecuta esta acción")
    targetPlayerId: Optional[int] = Field(None, description="ID del jugador objetivo (requerido para selectPlayer)")
    secretId: Optional[int] = Field(None, description="ID del secreto en CardsXGame (requerido para selectSecret)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "actionId": 505,
                "executorId": 12,
                "targetPlayerId": 13,
                "secretId": 234
            }
        }


class RevealedSecret(BaseModel):
    """Secreto que fue revelado - info completa para la UI"""
    playerId: int = Field(..., description="ID del jugador dueño del secreto")
    secretId: int = Field(..., description="ID de la carta en CardsXGame")
    cardId: int = Field(..., description="ID de la carta (Card.id)")
    cardName: str = Field(..., description="Nombre de la carta revelada")
    imgSrc: str = Field(..., description="Ruta de la imagen de la carta")
    position: int = Field(..., description="Posición del secreto en el set")
    
    class Config:
        json_schema_extra = {
            "example": {
                "playerId": 13,
                "secretId": 234,
                "cardId": 2,
                "cardName": "You are the Murderer!!",
                "imgSrc": "/assets/cards/murderer.png",
                "position": 1
            }
        }


class HiddenSecret(BaseModel):
    """Secreto que fue ocultado (Parker Pyne) - vuelve a estar oculto"""
    playerId: int = Field(..., description="ID del jugador dueño del secreto")
    secretId: int = Field(..., description="ID de la carta en CardsXGame")
    position: int = Field(..., description="Posición del secreto en el set")
    
    class Config:
        json_schema_extra = {
            "example": {
                "playerId": 13,
                "secretId": 234,
                "position": 1
            }
        }


class TransferredSecret(BaseModel):
    """Secreto que fue transferido (Satterthwaite con comodín)"""
    fromPlayerId: int = Field(..., description="ID del jugador que pierde el secreto")
    toPlayerId: int = Field(..., description="ID del jugador que recibe el secreto")
    secretId: int = Field(..., description="ID de la carta en CardsXGame")
    cardId: int = Field(..., description="ID de la carta (Card.id)")
    cardName: str = Field(..., description="Nombre de la carta transferida")
    imgSrc: str = Field(..., description="Ruta de la imagen de la carta")
    faceDown: bool = Field(True, description="Si el secreto se transfiere boca abajo (oculto para otros)")
    newPosition: int = Field(..., description="Nueva posición del secreto en el set del nuevo dueño")
    
    class Config:
        json_schema_extra = {
            "example": {
                "fromPlayerId": 13,
                "toPlayerId": 12,
                "secretId": 234,
                "cardId": 2,
                "cardName": "You are the Murderer!!",
                "imgSrc": "/assets/cards/murderer.png",
                "faceDown": True,
                "newPosition": 4
            }
        }


class EffectsSummary(BaseModel):
    """Resumen de efectos aplicados para la UI"""
    revealed: List[RevealedSecret] = Field(
        default_factory=list, 
        description="Secretos que fueron revelados"
    )
    hidden: List[HiddenSecret] = Field(
        default_factory=list, 
        description="Secretos que fueron ocultados"
    )
    transferred: List[TransferredSecret] = Field(
        default_factory=list, 
        description="Secretos que fueron transferidos"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "revealed": [
                    {
                        "playerId": 13,
                        "secretId": 234,
                        "cardId": 2,
                        "position": 1
                    }
                ],
                "hidden": [],
                "transferred": []
            }
        }


class DetectiveActionResponse(BaseModel):
    """Response al ejecutar una acción de detective"""
    success: bool = Field(..., description="Si la acción se ejecutó exitosamente")
    completed: bool = Field(
        ..., 
        description="True si la acción está completamente terminada (no hay más pasos)"
    )
    nextAction: Optional[NextAction] = Field(
        None, 
        description="Si hay más pasos pendientes, indica qué tipo de acción sigue"
    )
    effects: EffectsSummary = Field(
        default_factory=EffectsSummary, 
        description="Resumen de efectos aplicados en este paso"
    )
    
    @validator('nextAction')
    def validate_next_action_when_not_completed(cls, v, values):
        """Si completed=False, debe haber nextAction"""
        if 'completed' in values and not values['completed'] and v is None:
            raise ValueError("nextAction is required when completed=False")
        if 'completed' in values and values['completed'] and v is not None:
            raise ValueError("nextAction must be None when completed=True")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "completed": True,
                "nextAction": None,
                "effects": {
                    "revealed": [
                        {
                            "playerId": 13,
                            "secretId": 234,
                            "cardId": 2,
                            "position": 1
                        }
                    ],
                    "hidden": [],
                    "transferred": []
                }
            }
        }

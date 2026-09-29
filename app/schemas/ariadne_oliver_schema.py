"""
Schemas for Ariadne Oliver detective card endpoints.

Ariadne Oliver allows a player to add this detective card to ANY existing 
detective set owned by another player. Then, the owner of that set must 
reveal one of their own secrets as a penalty.
"""

from pydantic import BaseModel, Field
from typing import Optional


class AddOliverToSetRequest(BaseModel):
    """
    Request para agregar Ariadne Oliver a un set existente de otro jugador.
    
    El jugador que tiene Ariadne Oliver en su mano la juega agregándola
    al set de detective de otro jugador.
    """
    player_id: int = Field(..., description="ID del jugador que juega Ariadne Oliver")
    oliver_card_id: int = Field(..., description="ID de CardsXGame de la carta Ariadne Oliver")
    target_player_id: int = Field(..., description="ID del jugador dueño del set objetivo")
    target_set_position: int = Field(..., description="Posición del set de detective objetivo")

    class Config:
        json_schema_extra = {
            "example": {
                "player_id": 1,
                "oliver_card_id": 42,
                "target_player_id": 3,
                "target_set_position": 2
            }
        }


class AddOliverToSetResponse(BaseModel):
    """
    Response del endpoint de agregar Ariadne Oliver a un set.
    
    Retorna el ID de la acción creada y el mensaje de confirmación.
    """
    status: str = Field(..., description="Estado de la operación (success/error)")
    action_id: int = Field(..., description="ID de la acción padre creada (ADD_DETECTIVE)")
    next_action: str = Field(..., description="Siguiente paso en el flujo (WAIT_TARGET_REVEAL)")
    message: str = Field(..., description="Mensaje descriptivo de la acción")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "action_id": 123,
                "next_action": "WAIT_TARGET_REVEAL",
                "message": "Jugador Alice jugó Ariadne Oliver contra Jugador Bob"
            }
        }


class OliverRevealSecretRequest(BaseModel):
    """
    Request para que el jugador objetivo revele un secreto propio.
    
    El dueño del set (target_player) debe seleccionar uno de sus secretos
    para revelar como efecto de Ariadne Oliver.
    """
    action_id: int = Field(..., description="ID de la acción padre ADD_DETECTIVE")
    secret_id: int = Field(..., description="ID de CardsXGame del secreto a revelar")
    player_id: int = Field(..., description="ID del jugador que revela su secreto (target_player)")

    class Config:
        json_schema_extra = {
            "example": {
                "action_id": 123,
                "secret_id": 56,
                "player_id": 3
            }
        }


class OliverRevealSecretResponse(BaseModel):
    """
    Response del endpoint de revelar secreto por efecto de Ariadne Oliver.
    
    Indica si la revelación fue exitosa y retorna mensaje descriptivo.
    """
    status: str = Field(..., description="Estado de la operación (success/error)")
    message: str = Field(..., description="Mensaje descriptivo de la acción")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Jugador Bob reveló un secreto! Efecto de Ariadne terminado."
            }
        }

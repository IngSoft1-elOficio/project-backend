"""
Schemas for Dead Card Folly event card endpoints.

Dead Card Folly permite a un jugador elegir una dirección (LEFT/RIGHT) y
todos los jugadores intercambian una carta con su vecino en esa dirección.
"""

from pydantic import BaseModel, Field
from typing import Optional
from app.db.models import Direction


class PlayDeadCardFollyRequest(BaseModel):
    """
    Request para jugar la carta Dead Card Folly.
    
    El jugador juega la carta evento y elige una dirección.
    Esto inicia el proceso de intercambio de cartas.
    """
    player_id: int = Field(..., description="ID del jugador que juega la carta")
    card_id: int = Field(..., description="ID de CardsXGame de la carta Dead Card Folly")
    direction: Direction = Field(..., description="Dirección del intercambio (LEFT o RIGHT)")

    class Config:
        use_enum_values = True


class PlayDeadCardFollyResponse(BaseModel):
    """
    Response del endpoint de jugar Dead Card Folly.
    
    Retorna el ID de la acción creada para que los jugadores
    puedan seleccionar sus cartas.
    """
    success: bool = Field(..., description="Indica si la acción fue exitosa")
    action_id: int = Field(..., description="ID de la acción padre creada")


class SelectCardRequest(BaseModel):
    """
    Request para seleccionar la carta a intercambiar.
    
    Cada jugador usa este endpoint para elegir qué carta
    de su mano quiere pasar a su vecino.
    """
    action_id: int = Field(..., description="ID de la acción padre Dead Card Folly")
    card_id: int = Field(..., description="ID de CardsXGame de la carta elegida")
    player_id: int = Field(..., description="ID del jugador que selecciona")


class SelectCardResponse(BaseModel):
    """
    Response del endpoint de seleccionar carta.
    
    Indica si todavía se está esperando a otros jugadores
    o si la rotación ya se completó.
    """
    success: bool = Field(..., description="Indica si la selección fue exitosa")
    waiting: bool = Field(..., description="True si aún faltan jugadores por seleccionar")
    pending_count: int = Field(..., description="Cantidad de jugadores que faltan por seleccionar")
    message: str = Field(..., description="Mensaje descriptivo del estado")

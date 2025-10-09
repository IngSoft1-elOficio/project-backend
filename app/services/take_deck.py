from sqlalchemy.orm import Session
from app.db.models import CardsXGame, CardState, Game
from typing import List

async def robar_cartas_del_mazo(db, game, user_id, cantidad):
    print(f"🎴 Robando {cantidad} carta(s) del mazo para jugador {user_id}")
    
    drawn = (
        db.query(CardsXGame)
        .filter(CardsXGame.id_game == game.id,
                CardsXGame.is_in == CardState.DECK)
        .order_by(CardsXGame.position)  
        .limit(cantidad)
        .all()
    )
    for card in drawn:
        # resetear dueño
        card.player_id = user_id
        card.is_in = CardState.HAND
        print(f"  ✓ Carta {card.id_card} ({card.card.name if card.card else 'N/A'}) → mano del jugador")

    db.commit()
    print(f"✅ Total robado: {len(drawn)} carta(s)")
    return drawn
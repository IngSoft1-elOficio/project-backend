# app/services/discard.py
from sqlalchemy.orm import Session
from app.db.models import CardsXGame, CardState, Game
from typing import List

async def descartar_cartas(db, game, user_id, ordered_player_cards):
    discarded = []

    next_pos = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DISCARD
    ).count()
    print(f"🔢 Próxima posición en descarte: {next_pos}")

    for i, card in enumerate(ordered_player_cards):
        # Eliminar duplicados (si existen)
        db.query(CardsXGame).filter(
            CardsXGame.id_game == game.id,
            CardsXGame.id_card == card.id_card,
            CardsXGame.player_id == user_id,
            CardsXGame.is_in != CardState.HAND
        ).delete(synchronize_session=False)
        
        # Descartar la carta (ya tenemos el objeto, no necesitamos buscarlo)
        card.is_in = CardState.DISCARD
        card.position = next_pos + i  # Ahora i empieza en 0, así que está bien
        discarded.append(card)
        
        print(f"  Carta {card.id_card} → posición {card.position}")
    
    db.commit()
    print(f"✅ Total descartado en orden: {[c.id_card for c in discarded]}")
    return discarded
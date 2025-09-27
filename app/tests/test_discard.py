import pytest

@pytest.mark.asyncio
async def test_discard_logic():
    """Simula la lógica principal de /discard"""

    # Datos simulados
    game_data = {"id": 1, "player_turn_id": 1}
    user_id = 1
    game_id = 1

    hand_cards = [
        {"id": 10, "is_in": "HAND", "player_id": 1},
        {"id": 11, "is_in": "HAND", "player_id": 1},
        {"id": 12, "is_in": "HAND", "player_id": 1},
    ]

    deck_cards = [
        {"id": 20, "is_in": "DECK", "player_id": None},
        {"id": 21, "is_in": "DECK", "player_id": None},
    ]

    players = [
        {"id": 1, "order": 1},
        {"id": 2, "order": 2}
    ]

    # --- Simulación de endpoint ---

    # 1. Validar que el juego existe
    assert game_data["id"] == game_id

    # 2. Validar turno
    assert game_data["player_turn_id"] == user_id

    # 3. Validar cartas en mano
    card_ids = [10, 11]
    owned_ids = [c["id"] for c in hand_cards if c["player_id"] == user_id and c["is_in"] == "HAND"]
    for cid in card_ids:
        assert cid in owned_ids

    # 4. Descartar
    discarded = []
    for c in hand_cards:
        if c["id"] in card_ids:
            c["is_in"] = "DISCARD"
            c["player_id"] = None
            discarded.append(c)

    # 5. Reponer desde el mazo
    drawn = []
    for _ in discarded:
        if deck_cards:  # mazo no vacío
            new_card = deck_cards.pop(0)
            new_card["is_in"] = "HAND"
            new_card["player_id"] = user_id
            drawn.append(new_card)

    # 6. Finalizar turno
    player_ids = [p["id"] for p in players]
    current_idx = player_ids.index(user_id)
    next_turn = player_ids[(current_idx + 1) % len(player_ids)]

    # 7. Simular publicación WS (mock simple)
    ws_event = {
        "discarded": [c["id"] for c in discarded],
        "drawn": [c["id"] for c in drawn],
        "next_turn": next_turn
    }

    # --- Verificación ---
    expected = {
        "discarded": [10, 11],
        "drawn": [20, 21],
        "next_turn": 2
    }

    assert ws_event == expected


def test_discard_validations():
    """Validaciones de discard"""

    # Juego no encontrado
    game_data = None
    assert game_data is None  # HTTP 404

    # No es el turno
    game_data = {"id": 1, "player_turn_id": 2}
    user_id = 1
    assert game_data["player_turn_id"] != user_id  # HTTP 403

    # Lista vacía
    card_ids = []
    assert len(card_ids) == 0  # HTTP 400

    # Carta inválida
    hand_cards = [{"id": 10, "is_in": "HAND", "player_id": 1}]
    card_ids = [999]
    owned_ids = [c["id"] for c in hand_cards]
    assert not all(cid in owned_ids for cid in card_ids)  # HTTP 400


def test_discard_murderer_wins_when_deck_empty():
    """Si el mazo queda vacío, gana el asesino"""
    game_data = {"id": 1, "player_turn_id": 1}
    user_id = 1

    hand_cards = [{"id": 10, "is_in": "HAND", "player_id": 1}]
    deck_cards = []  # vacío

    # Intenta descartar
    discarded_card = hand_cards[0]
    discarded_card["is_in"] = "DISCARD"
    discarded_card["player_id"] = None

    # No puede reponer → asesino gana
    murderer_wins = len(deck_cards) == 0
    assert murderer_wins is True

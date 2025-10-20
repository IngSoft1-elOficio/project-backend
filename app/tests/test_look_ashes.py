import pytest
import uuid
from fastapi.testclient import TestClient
from app.db.database import Base, engine, SessionLocal
from app.db import crud, models
from app.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield
    db.close()

def create_game_room_player(db):
    # Create card types
    event_card = models.Card(name="Look Into The Ashes", description="event", type=models.CardType.EVENT, img_src="x", qty=1)
    other_card = models.Card(name="Some Card", description="c", type=models.CardType.INSTANT, img_src="i", qty=2)
    db.add(event_card)
    db.add(other_card)
    db.commit()
    db.refresh(event_card)
    db.refresh(other_card)

    # Create game, room, player, turn
    game = crud.create_game(db, {})
    room = crud.create_room(db, {'name': 'r1', 'status': models.RoomStatus.INGAME, 'id_game': game.id})
    # Use a unique player name per test run to avoid UniqueConstraint collisions
    player_name = f"p1-{uuid.uuid4().hex[:8]}"
    player = crud.create_player(db, {'name': player_name, 'avatar_src': 'a', 'birthdate': '2000-01-01', 'id_room': room.id, 'order': 1})
    # set game.player_turn_id
    crud.update_player_turn(db, game.id, player.id)
    # create turn
    turn = models.Turn(number=1, id_game=game.id, player_id=player.id, status=models.TurnStatus.IN_PROGRESS)
    db.add(turn)
    db.commit()
    db.refresh(turn)

    return {
        'game': game,
        'room': room,
        'player': player,
        'event_card': event_card,
        'other_card': other_card,
        'turn': turn
    }

def test_play_with_empty_discard_returns_400():
    db = SessionLocal()
    data = create_game_room_player(db)

    # assign event card to player's hand
    event_entry = models.CardsXGame(id_game=data['game'].id, id_card=data['event_card'].id, is_in=models.CardState.HAND, position=0, player_id=data['player'].id, hidden=True)
    db.add(event_entry)
    db.commit()
    db.refresh(event_entry)

    payload = {"card_id": event_entry.id}
    headers = {"http-user-id": str(data['player'].id)}

    resp = client.post(f"/api/game/{data['room'].id}/look-into-ashes/play", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.json()['detail'] == 'Discard pile is empty'

def test_play_with_discard_and_select_flow():
    db = SessionLocal()
    data = create_game_room_player(db)

    # assign event card to player's hand
    event_entry = models.CardsXGame(id_game=data['game'].id, id_card=data['event_card'].id, is_in=models.CardState.HAND, position=0, player_id=data['player'].id, hidden=True)
    db.add(event_entry)

    # create two discard cards
    disc1 = models.CardsXGame(id_game=data['game'].id, id_card=data['other_card'].id, is_in=models.CardState.DISCARD, position=5, player_id=None, hidden=False)
    disc2 = models.CardsXGame(id_game=data['game'].id, id_card=data['other_card'].id, is_in=models.CardState.DISCARD, position=4, player_id=None, hidden=False)
    db.add(disc1)
    db.add(disc2)
    db.commit()
    db.refresh(event_entry)
    db.refresh(disc1)
    db.refresh(disc2)

    payload = {"card_id": event_entry.id}
    headers = {"http-user-id": str(data['player'].id)}

    # play
    resp = client.post(f"/api/game/{data['room'].id}/look-into-ashes/play", json=payload, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    action_id = body['action_id']
    assert isinstance(action_id, int)
    available = body['available_cards']
    assert len(available) == 2
    # pick the top discard (position 5 -> first element)
    selected_entry_id = available[0]['entryId']

    # select the card
    select_payload = {"action_id": action_id, "selected_card_id": selected_entry_id}
    resp2 = client.post(f"/api/game/{data['room'].id}/look-into-ashes/select", json=select_payload, headers=headers)
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2['success'] is True
    assert 'card_taken' in body2
    # verify that selected card is now in player's hand in DB
    db2 = SessionLocal()
    try:
        taken = db2.query(models.CardsXGame).filter(models.CardsXGame.id == selected_entry_id).first()
        assert taken is not None
        assert taken.player_id == data['player'].id
        assert taken.is_in == models.CardState.HAND
    finally:
        db2.close()

def test_select_invalid_card_returns_400():
    db = SessionLocal()
    data = create_game_room_player(db)

    # create action that would correspond to a play
    action = crud.create_action(db, {'id_game': data['game'].id, 'turn_id': data['turn'].id, 'player_id': data['player'].id, 'action_name': models.ActionName.LOOK_INTO_THE_ASHES.value, 'action_type': models.ActionType.EVENT_CARD, 'result': models.ActionResult.SUCCESS})
    db.commit()
    db.refresh(action)

    # No discard cards
    headers = {"http-user-id": str(data['player'].id)}
    select_payload = {"action_id": action.id, "selected_card_id": 9999}
    resp = client.post(f"/api/game/{data['room'].id}/look-into-ashes/select", json=select_payload, headers=headers)
    assert resp.status_code == 400
    assert 'Selected card is not in the top 5' in resp.json()['detail'] or 'Invalid parent action' not in resp.json()['detail']

def test_play_room_not_found():
    # calling play with non-existent room should 404
    payload = {"card_id": 1}
    headers = {"http-user-id": "1"}
    resp = client.post(f"/api/game/99999/look-into-ashes/play", json=payload, headers=headers)
    assert resp.status_code == 404
    assert resp.json()['detail'] == 'Room not found'

def test_play_room_has_no_active_game():
    db = SessionLocal()
    # create a room without id_game
    room = crud.create_room(db, {'name': 'no_game_room', 'status': models.RoomStatus.WAITING})
    headers = {"http-user-id": "1"}
    payload = {"card_id": 1}
    resp = client.post(f"/api/game/{room.id}/look-into-ashes/play", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.json()['detail'] == 'Room has no active game'

def test_play_game_not_found(monkeypatch):
    db = SessionLocal()
    # create a real game and room
    game = crud.create_game(db, {})
    room = crud.create_room(db, {'name': 'room_bad_game', 'status': models.RoomStatus.INGAME, 'id_game': game.id})
    # monkeypatch crud.get_game_by_id to simulate missing game
    monkeypatch.setattr(crud, 'get_game_by_id', lambda db_sess, gid: None)
    headers = {"http-user-id": "1"}
    payload = {"card_id": 1}
    resp = client.post(f"/api/game/{room.id}/look-into-ashes/play", json=payload, headers=headers)
    assert resp.status_code == 404
    assert resp.json()['detail'] == 'Game not found'

def test_play_not_your_turn():
    db = SessionLocal()
    # create game and two players; set player_turn to player1
    game = crud.create_game(db, {})
    room = crud.create_room(db, {'name': 'rnt', 'status': models.RoomStatus.INGAME, 'id_game': game.id})
    player1 = crud.create_player(db, {'name': f'pt1-{uuid.uuid4().hex[:6]}', 'avatar_src': 'a', 'birthdate': '2000-01-01', 'id_room': room.id, 'order': 1})
    player2 = crud.create_player(db, {'name': f'pt2-{uuid.uuid4().hex[:6]}', 'avatar_src': 'a', 'birthdate': '2000-01-01', 'id_room': room.id, 'order': 2})
    crud.update_player_turn(db, game.id, player1.id)
    headers = {"http-user-id": str(player2.id)}
    payload = {"card_id": 1}
    resp = client.post(f"/api/game/{room.id}/look-into-ashes/play", json=payload, headers=headers)
    assert resp.status_code == 403
    assert resp.json()['detail'] == 'Not your turn'

def test_play_event_card_not_in_hand():
    db = SessionLocal()
    data = create_game_room_player(db)
    # create an event card entry but not in player's hand
    ev_entry = models.CardsXGame(id_game=data['game'].id, id_card=data['event_card'].id, is_in=models.CardState.DISCARD, position=1, player_id=None, hidden=False)
    db.add(ev_entry)
    db.commit()
    headers = {"http-user-id": str(data['player'].id)}
    payload = {"card_id": ev_entry.id}
    resp = client.post(f"/api/game/{data['room'].id}/look-into-ashes/play", json=payload, headers=headers)
    assert resp.status_code == 404
    assert resp.json()['detail'] == 'Event card not found in your hand'

def test_play_card_not_event_type():
    db = SessionLocal()
    data = create_game_room_player(db)
    # create a non-event card entry in player's hand
    non_event = models.Card(name='n', description='n', type=models.CardType.INSTANT, img_src='i', qty=1)
    db.add(non_event)
    db.commit()
    db.refresh(non_event)
    entry = models.CardsXGame(id_game=data['game'].id, id_card=non_event.id, is_in=models.CardState.HAND, position=0, player_id=data['player'].id, hidden=True)
    db.add(entry)
    db.commit()
    headers = {"http-user-id": str(data['player'].id)}
    payload = {"card_id": entry.id}
    resp = client.post(f"/api/game/{data['room'].id}/look-into-ashes/play", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.json()['detail'] == 'Card is not an event card'

def test_play_no_current_turn():
    db = SessionLocal()
    # create game and room and player but no Turn
    game = crud.create_game(db, {})
    room = crud.create_room(db, {'name': 'rcnt', 'status': models.RoomStatus.INGAME, 'id_game': game.id})
    player = crud.create_player(db, {'name': f'pcnt-{uuid.uuid4().hex[:6]}', 'avatar_src': 'a', 'birthdate': '2000-01-01', 'id_room': room.id, 'order': 1})
    crud.update_player_turn(db, game.id, player.id)
    # put an event card in hand
    ev = models.Card(name='e', description='e', type=models.CardType.EVENT, img_src='i', qty=1)
    db.add(ev)
    db.commit()
    db.refresh(ev)
    entry = models.CardsXGame(id_game=game.id, id_card=ev.id, is_in=models.CardState.HAND, position=0, player_id=player.id, hidden=True)
    db.add(entry)
    db.commit()
    headers = {"http-user-id": str(player.id)}
    payload = {"card_id": entry.id}
    # create a discard card so the discard check passes and the code reaches turn check
    dcard = models.CardsXGame(id_game=game.id, id_card=ev.id, is_in=models.CardState.DISCARD, position=1, player_id=None, hidden=False)
    db.add(dcard)
    db.commit()
    resp = client.post(f"/api/game/{room.id}/look-into-ashes/play", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.json()['detail'] == 'No active turn found'

def test_select_room_and_game_not_found():
    # room not found
    payload = {"action_id": 1, "selected_card_id": 1}
    headers = {"http-user-id": "1"}
    resp = client.post(f"/api/game/999999/look-into-ashes/select", json=payload, headers=headers)
    assert resp.status_code == 404
    # create a room pointing to bad game
    db = SessionLocal()
    game = crud.create_game(db, {})
    room = crud.create_room(db, {'name': 'sgnf', 'status': models.RoomStatus.INGAME, 'id_game': game.id})
    # monkeypatch get_game_by_id to return None to simulate missing game
    import types
    from unittest.mock import patch
    with patch('app.db.crud.get_game_by_id', return_value=None):
        resp2 = client.post(f"/api/game/{room.id}/look-into-ashes/select", json=payload, headers=headers)
    assert resp2.status_code == 404

def test_select_parent_action_not_found_and_invalid_and_expired():
    db = SessionLocal()
    data = create_game_room_player(db)
    headers = {"http-user-id": str(data['player'].id)}
    # parent action not found
    payload = {"action_id": 999999, "selected_card_id": 1}
    resp = client.post(f"/api/game/{data['room'].id}/look-into-ashes/select", json=payload, headers=headers)
    assert resp.status_code == 404

    # create a parent action that belongs to different player -> invalid
    other_player = crud.create_player(db, {'name': f'op-{uuid.uuid4().hex[:6]}', 'avatar_src': 'a', 'birthdate': '2000-01-01', 'id_room': data['room'].id, 'order': 99})
    action = crud.create_action(db, {'id_game': data['game'].id, 'turn_id': data['turn'].id, 'player_id': other_player.id, 'action_name': models.ActionName.LOOK_INTO_THE_ASHES.value, 'action_type': models.ActionType.EVENT_CARD, 'result': models.ActionResult.SUCCESS})
    db.commit()
    db.refresh(action)
    payload2 = {"action_id": action.id, "selected_card_id": 1}
    resp2 = client.post(f"/api/game/{data['room'].id}/look-into-ashes/select", json=payload2, headers=headers)
    assert resp2.status_code == 400
    # create an expired action (older than 10 minutes)
    from datetime import datetime, timedelta
    old_time = datetime.now() - timedelta(minutes=11)
    action2 = crud.create_action(db, {'id_game': data['game'].id, 'turn_id': data['turn'].id, 'player_id': data['player'].id, 'action_name': models.ActionName.LOOK_INTO_THE_ASHES.value, 'action_type': models.ActionType.EVENT_CARD, 'result': models.ActionResult.SUCCESS, 'action_time': old_time})
    db.commit()
    db.refresh(action2)
    payload3 = {"action_id": action2.id, "selected_card_id": 1}
    resp3 = client.post(f"/api/game/{data['room'].id}/look-into-ashes/select", json=payload3, headers=headers)
    assert resp3.status_code == 400
    assert resp3.json()['detail'] == 'Action expired'

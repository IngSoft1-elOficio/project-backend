# app/tests/test_add_to_set_service.py
import pytest
from fastapi import HTTPException
from unittest.mock import Mock, patch
from app.services.detective_set_service import DetectiveSetService
from app.schemas.detective_set_schema import addDetectiveToSetRequest, SetType
from app.db.models import ActionType, ActionResult, CardState

class TestAddToSetService:
    def test_equivalente_exitoso(self):
        """Equivalente - flujo exitoso"""
        db = Mock()
        svc = DetectiveSetService(db)
        req = addDetectiveToSetRequest(owner=1, setType=SetType.BERESFORD, card=8, setPosition=1)
        with pytest.MonkeyPatch.context() as m:
            import app.services.detective_set_service as mod
            m.setattr(mod.crud, "get_game_by_id", lambda db, id: Mock(id=1, player_turn_id=1))
            m.setattr(mod.crud, "get_player_by_id", lambda db, id: Mock(id=1, room=Mock(id_game=1)))
            m.setattr(mod.crud, "get_active_turn_for_player", lambda db, g, p: Mock(id=1))
            m.setattr(mod.crud, "get_cards_in_hand_by_ids", lambda db, c, p, g: [Mock(id_card=8)])
            m.setattr(mod.crud, "update_cards_state", lambda *a, **kw: None)
            m.setattr(mod.crud, "create_action", lambda db, data: Mock(id=5))
            m.setattr(mod.crud, "get_players_not_in_disgrace", lambda db, g, p: [2])
            m.setattr(mod.crud, "get_max_position_for_player_by_state", lambda *a, **kw: 1)
            action_id, next_action = svc.add_detective_to_set(1, req)
            assert action_id == 5
            assert next_action.type.value == "selectPlayer"

    def test_equivalente_carta_no_en_mano(self):
        """Equivalente - carta no en mano"""
        db = Mock()
        svc = DetectiveSetService(db)
        req = addDetectiveToSetRequest(owner=1, setType=SetType.MARPLE, card=99, setPosition=1)
        with pytest.MonkeyPatch.context() as m:
            import app.services.detective_set_service as mod
            m.setattr(mod.crud, "get_game_by_id", lambda db, id: Mock(id=1))
            m.setattr(mod.crud, "get_player_by_id", lambda db, id: Mock(id=1, room=Mock(id_game=1)))
            m.setattr(mod.crud, "get_active_turn_for_player", lambda *a, **kw: Mock(id=1))
            m.setattr(mod.crud, "get_cards_in_hand_by_ids", lambda *a, **kw: [])
            with pytest.raises(HTTPException):
                svc.add_detective_to_set(1, req)

    def test_equivalente_set_inexistente(self):
        """Equivalente - set inexistente"""
        db = Mock()
        svc = DetectiveSetService(db)
        req = addDetectiveToSetRequest(owner=1, setType=SetType.MARPLE, card=6, setPosition=99)
        with pytest.MonkeyPatch.context() as m:
            import app.services.detective_set_service as mod
            m.setattr(mod.crud, "get_game_by_id", lambda *a, **kw: Mock(id=1, player_turn_id=1))
            m.setattr(mod.crud, "get_player_by_id", lambda *a, **kw: Mock(id=1, room=Mock(id_game=1)))
            m.setattr(mod.crud, "get_active_turn_for_player", lambda *a, **kw: Mock(id=1))
            m.setattr(mod.crud, "get_cards_in_hand_by_ids", lambda *a, **kw: [Mock(id_card=6)])
            m.setattr(mod.crud, "get_players_not_in_disgrace", lambda *a, **kw: [])
            m.setattr(mod.crud, "get_max_position_for_player_by_state", lambda *a, **kw: 1)
            # Simula sin cartas en set (count=0)
            from app.services.detective_set_service import CardsXGame, CardState
            svc.db.query = lambda model: Mock(filter=lambda *a, **kw: Mock(count=lambda: 0))
            with pytest.raises(HTTPException):
                svc.add_detective_to_set(1, req)

    def test_equivalente_carta_erronea_para_set(self):
        """Equivalente - carta errónea para tipo de set"""
        db = Mock()
        svc = DetectiveSetService(db)
        req = addDetectiveToSetRequest(owner=1, setType=SetType.MARPLE, card=99, setPosition=1)
        card = Mock(id_card=11)  # Poirot
        with pytest.MonkeyPatch.context() as m:
            import app.services.detective_set_service as mod
            m.setattr(mod.crud, "get_game_by_id", lambda *a, **kw: Mock(id=1, player_turn_id=1))
            m.setattr(mod.crud, "get_player_by_id", lambda *a, **kw: Mock(id=1, room=Mock(id_game=1)))
            m.setattr(mod.crud, "get_active_turn_for_player", lambda *a, **kw: Mock(id=1))
            m.setattr(mod.crud, "get_cards_in_hand_by_ids", lambda *a, **kw: [card])
            with pytest.raises(HTTPException):
                svc.add_detective_to_set(1, req)

    def test_borde_carta_wildcard(self):
        """Borde - carta comodín no permitida"""
        db = Mock()
        svc = DetectiveSetService(db)
        req = addDetectiveToSetRequest(owner=1, setType=SetType.MARPLE, card=4, setPosition=1)
        card = Mock(id_card=4)
        with pytest.MonkeyPatch.context() as m:
            import app.services.detective_set_service as mod
            m.setattr(mod.crud, "get_game_by_id", lambda *a, **kw: Mock(id=1, player_turn_id=1))
            m.setattr(mod.crud, "get_player_by_id", lambda *a, **kw: Mock(id=1, room=Mock(id_game=1)))
            m.setattr(mod.crud, "get_active_turn_for_player", lambda *a, **kw: Mock(id=1))
            m.setattr(mod.crud, "get_cards_in_hand_by_ids", lambda *a, **kw: [card])
            with pytest.raises(HTTPException) as exc:
                svc.add_detective_to_set(1, req)
            assert "Harley Quin" in str(exc.value.detail)

    def test_cb_flujo_completo_commit(self):
        """CajaBlanca - flujo completo con commit ejecutado"""
        db = Mock()
        svc = DetectiveSetService(db)
        req = addDetectiveToSetRequest(owner=1, setType=SetType.BERESFORD, card=8, setPosition=1)
        with patch("app.services.detective_set_service.crud") as crud:
            crud.get_game_by_id.return_value = Mock(id=1, player_turn_id=1)
            crud.get_player_by_id.return_value = Mock(id=1, room=Mock(id_game=1))
            crud.get_active_turn_for_player.return_value = Mock(id=1)
            crud.get_cards_in_hand_by_ids.return_value = [Mock(id_card=8)]
            crud.get_players_not_in_disgrace.return_value = [2, 3]
            crud.get_max_position_for_player_by_state.return_value = 1
            crud.update_cards_state.return_value = None
            crud.create_action.return_value = Mock(id=5)
            action_id, next_action = svc.add_detective_to_set(1, req)
            assert action_id == 5
            db.commit.assert_called_once()

    def test_cb_rama_excepcion_en_update_cards(self):
        """CajaBlanca - excepción durante update_cards_state"""
        db = Mock()
        svc = DetectiveSetService(db)
        req = addDetectiveToSetRequest(owner=1, setType=SetType.MARPLE, card=6, setPosition=1)
        with patch("app.services.detective_set_service.crud") as crud:
            crud.get_game_by_id.return_value = Mock(id=1, player_turn_id=1)
            crud.get_player_by_id.return_value = Mock(id=1, room=Mock(id_game=1))
            crud.get_active_turn_for_player.return_value = Mock(id=1)
            crud.get_cards_in_hand_by_ids.return_value = [Mock(id_card=6)]
            crud.get_players_not_in_disgrace.return_value = []
            crud.get_max_position_for_player_by_state.return_value = 1
            crud.update_cards_state.side_effect = Exception("DB fail")
            with pytest.raises(HTTPException) as exc:
                svc.add_detective_to_set(1, req)
            assert exc.value.status_code == 500
            assert "Internal error" in str(exc.value.detail)

    def test_cb_rama_turno_incorrecto(self):
        """CajaBlanca - rama que lanza error cuando no es su turno"""
        db = Mock()
        svc = DetectiveSetService(db)
        req = addDetectiveToSetRequest(owner=2, setType=SetType.BERESFORD, card=8, setPosition=1)
        with patch("app.services.detective_set_service.crud") as crud:
            crud.get_game_by_id.return_value = Mock(id=1, player_turn_id=99)
            crud.get_player_by_id.return_value = Mock(id=2, room=Mock(id_game=1))
            crud.get_active_turn_for_player.return_value = Mock(id=1)
            crud.get_cards_in_hand_by_ids.return_value = [Mock(id_card=8)]
            with pytest.raises(HTTPException) as exc:
                svc.add_detective_to_set(1, req)
            assert exc.value.status_code == 403

    def test_cb_rama_commit_falla(self):
        """CajaBlanca - commit lanza excepción (rollback esperado)"""
        db = Mock()
        db.commit.side_effect = Exception("DB Commit failed")
        svc = DetectiveSetService(db)
        req = addDetectiveToSetRequest(owner=1, setType=SetType.MARPLE, card=6, setPosition=1)
        with patch("app.services.detective_set_service.crud") as crud:
            crud.get_game_by_id.return_value = Mock(id=1, player_turn_id=1)
            crud.get_player_by_id.return_value = Mock(id=1, room=Mock(id_game=1))
            crud.get_active_turn_for_player.return_value = Mock(id=1)
            crud.get_cards_in_hand_by_ids.return_value = [Mock(id_card=6)]
            crud.create_action.return_value = Mock(id=99)
            crud.get_players_not_in_disgrace.return_value = []
            with pytest.raises(HTTPException):
                svc.add_detective_to_set(1, req)
            db.rollback.assert_called_once()
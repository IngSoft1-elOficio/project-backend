USE cards_table_develop;

-- ==============================
-- NSF Test Data
-- Configuración para probar el flujo completo de Not So Fast
-- ==============================

-- ==============================
-- Create Game
-- ==============================
INSERT INTO game (id, player_turn_id) VALUES (1, NULL);

-- ==============================
-- Create Room
-- ==============================
INSERT INTO room (name, players_min, players_max, password, status, id_game) VALUES
('NSF Test Room', 3, 3, NULL, 'INGAME', 1);

-- ==============================
-- Create Players
-- ==============================
INSERT INTO player (name, avatar_src, birthdate, id_room, is_host, `order`) VALUES
('NSF_Player1', '/avatars/nsf_p1.jpg', '1990-01-01', 1, TRUE, 1),
('NSF_Player2', '/avatars/nsf_p2.jpg', '1990-02-02', 1, FALSE, 2),
('NSF_Player3', '/avatars/nsf_p3.jpg', '1990-03-03', 1, FALSE, 3);

-- Actualizar player_turn_id al primer jugador
UPDATE game SET player_turn_id = 1 WHERE id = 1;

-- ==============================
-- Create Turn
-- ==============================
INSERT INTO turn (number, id_game, player_id, status, start_time) VALUES
(1, 1, 1, 'IN_PROGRESS', NOW());

-- ==============================
-- CardsXGame - Distribución de cartas
-- ==============================

-- ============================================================
-- PLAYER 1 (NSF_Player1) - Jugador que inicia la acción
-- ============================================================
-- HAND (6 cartas: 1 NSF + Point Suspicions + 4 más)
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 13, 'HAND', 1, 1, true),  -- NSF (card_id=13)
(1, 17, 'HAND', 2, 1, true),  -- Point Your Suspicions (card_id=17, cancelable)
(1, 4, 'HAND', 3, 1, true),   -- Harley Quin Wildcard
(1, 5, 'HAND', 4, 1, true),   -- Ariadne Oliver
(1, 7, 'HAND', 5, 1, true),  -- Parker Pyne
(1, 7, 'HAND', 6, 1, true);  -- Parker Pyne

-- SECRETS (3 secretos ocultos)
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 3, 'SECRET_SET', 1, 1, true),  -- Secret Card
(1, 3, 'SECRET_SET', 2, 1, true),  -- Secret Card
(1, 3, 'SECRET_SET', 3, 1, true);  -- Secret Card

-- ============================================================
-- PLAYER 2 (NSF_Player2) - Jugará NSF primero
-- ============================================================
-- HAND (6 cartas: 1 NSF + 5 más)
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 13, 'HAND', 1, 2, true),  -- NSF (card_id=13)
(1, 6, 'HAND', 2, 2, true),   -- Miss Marple
(1, 21, 'HAND', 3, 2, true),   -- Card Trade
(1, 18, 'HAND', 4, 2, true),  -- Dead Card Folly
(1, 19, 'HAND', 5, 2, true),  -- Another Victim
(1, 22, 'HAND', 6, 2, true);  -- One More

-- SECRETS (3 secretos ocultos)
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 3, 'SECRET_SET', 1, 2, true),  -- Secret Card
(1, 3, 'SECRET_SET', 2, 2, true),  -- Secret Card
(1, 3, 'SECRET_SET', 3, 2, true);  -- Secret Card

-- ============================================================
-- PLAYER 3 (NSF_Player3) - Jugará NSF segundo
-- ============================================================
-- HAND (6 cartas: 1 NSF + 5 más)
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 13, 'HAND', 1, 3, true),  -- NSF (card_id=13)
(1, 8, 'HAND', 2, 3, true),   -- Tommy Beresford
(1, 10, 'HAND', 3, 3, true),  -- Tuppence Beresford
(1, 11, 'HAND', 4, 3, true),  -- Hercule Poirot
(1, 16, 'HAND', 5, 3, true),  -- Delay the Murderer's Escape
(1, 23, 'HAND', 6, 3, true);  -- Early Train to Paddington

-- SECRETS (3 secretos ocultos)
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 1, 'SECRET_SET', 1, 3, true),  -- Accomplice
(1, 3, 'SECRET_SET', 2, 3, true),  -- Secret Card
(1, 3, 'SECRET_SET', 3, 3, true);  -- Secret Card

-- ============================================================
-- DISCARD - 3 cartas iniciales
-- ============================================================
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 14, 'DISCARD', 1, NULL, false),  -- Social Faux Pas (tope visible)
(1, 15, 'DISCARD', 2, NULL, true),   -- Blackmailed (oculta)
(1, 12, 'DISCARD', 3, NULL, true);   -- Mr Satterthwaite (oculta)

-- ============================================================
-- DECK - Cartas restantes
-- ============================================================
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 9, 'DECK', 1, NULL, true),   -- Lady Bundle Brent
(1, 13, 'DECK', 2, NULL, true),  -- NSF
(1, 13, 'DECK', 3, NULL, true),  -- NSF
(1, 17, 'DECK', 4, NULL, true),  -- Point Suspicions
(1, 24, 'DECK', 5, NULL, true);  -- Cards off the Table

-- ============================================================
-- DRAFT - Vacío (no se usa en este test)
-- ============================================================
-- (sin cartas)

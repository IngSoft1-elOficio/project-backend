USE cards_table_develop;

-- ==============================
-- Ariadne Oliver Test Data
-- Configuración para probar el flujo completo de Ariadne Oliver
-- ==============================

-- ==============================
-- Create Game
-- ==============================
INSERT INTO game (id, player_turn_id) VALUES (1, NULL);

-- ==============================
-- Create Room
-- ==============================
INSERT INTO room (name, players_min, players_max, password, status, id_game) VALUES
('Ariadne Test Room', 3, 3, NULL, 'INGAME', 1);

-- ==============================
-- Create Players
-- ==============================
INSERT INTO player (name, avatar_src, birthdate, id_room, is_host, `order`) VALUES
('AO_Player1', '/avatars/ao_p1.jpg', '1990-01-01', 1, TRUE, 1),
('AO_Player2', '/avatars/ao_p2.jpg', '1990-02-02', 1, FALSE, 2),
('AO_Player3', '/avatars/ao_p3.jpg', '1990-03-03', 1, FALSE, 3);

-- Actualizar player_turn_id al primer jugador (quien tiene Ariadne Oliver)
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
-- PLAYER 1 (AO_Player1) - TURNO ACTUAL, TIENE ARIADNE OLIVER
-- ============================================================
-- HAND (6 cartas: Ariadne Oliver + 5 más)
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 5, 'HAND', 1, 1, true),   -- Ariadne Oliver (id_card=5) ← LA CARTA CLAVE
(1, 4, 'HAND', 2, 1, true),   -- Harley Quin Wildcard
(1, 6, 'HAND', 3, 1, true),   -- Miss Marple
(1, 8, 'HAND', 4, 1, true),   -- Tommy Beresford
(1, 10, 'HAND', 5, 1, true),  -- Tuppence Beresford
(1, 13, 'HAND', 6, 1, true);  -- Not So Fast

-- SECRETS (3 secretos ocultos)
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 3, 'SECRET_SET', 1, 1, true),  -- Secret Card
(1, 3, 'SECRET_SET', 2, 1, true),  -- Secret Card
(1, 3, 'SECRET_SET', 3, 1, true);  -- Secret Card

-- ============================================================
-- PLAYER 2 (AO_Player2) - TIENE UN SET DE DETECTIVE (PARKER PYNE)
-- ============================================================
-- HAND (6 cartas variadas)
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 11, 'HAND', 1, 2, true),  -- Hercule Poirot
(1, 9, 'HAND', 2, 2, true),   -- Lady Bundle Brent
(1, 21, 'HAND', 3, 2, true),  -- Card Trade
(1, 19, 'HAND', 4, 2, true),  -- Another Victim
(1, 22, 'HAND', 5, 2, true),  -- One More
(1, 18, 'HAND', 6, 2, true);  -- Dead Card Folly

-- DETECTIVE_SET (2 Parker Pyne en position 1) ← SET OBJETIVO PARA ARIADNE
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 7, 'DETECTIVE_SET', 1, 2, false),  -- Parker Pyne
(1, 7, 'DETECTIVE_SET', 1, 2, false);  -- Parker Pyne

-- SECRETS (3 secretos: 1 asesino + 2 normales)
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 2, 'SECRET_SET', 1, 2, true),  -- SE PUEDE CAMBIAR POR EL ASESINO, ID=2
(1, 3, 'SECRET_SET', 2, 2, true),  -- Secret Card
(1, 3, 'SECRET_SET', 3, 2, true);  -- Secret Card

-- ============================================================
-- PLAYER 3 (AO_Player3)
-- ============================================================
-- HAND (6 cartas variadas)
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 12, 'HAND', 1, 3, true),  -- Mr Satterthwaite
(1, 16, 'HAND', 2, 3, true),  -- Delay the Murderer's Escape
(1, 17, 'HAND', 3, 3, true),  -- Point Your Suspicions
(1, 23, 'HAND', 4, 3, true),  -- Early Train to Paddington
(1, 24, 'HAND', 5, 3, true),  -- Cards off the Table
(1, 13, 'HAND', 6, 3, true);  -- Not So Fast

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
(1, 7, 'DISCARD', 3, NULL, true);    -- Parker Pyne (oculta)

-- ============================================================
-- DECK - Cartas restantes
-- ============================================================
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(1, 13, 'DECK', 1, NULL, true),  -- NSF
(1, 13, 'DECK', 2, NULL, true),  -- NSF
(1, 13, 'DECK', 3, NULL, true),  -- NSF
(1, 20, 'DECK', 4, NULL, true);  -- Social Disgrace

-- ============================================================
-- DRAFT - Vacío (no se usa en este test)
-- ============================================================
-- (sin cartas)

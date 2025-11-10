-- ==============================
-- Testing Integral: Detective Action
-- ==============================
-- Este script NO borra datos existentes
-- Crea una partida en curso para testear play-detective-set

USE cards_table_develop;

-- ==============================
-- 1. Crear Game nuevo (probablemente id=2)
-- ==============================
INSERT INTO game (player_turn_id) VALUES (NULL);

SET @game_id = LAST_INSERT_ID();

-- ==============================
-- 2. Crear Room (probablemente id=4)
-- ==============================
INSERT INTO room (name, players_min, players_max, password, status, id_game) 
VALUES ('Test Detective', 3, 4, NULL, 'INGAME', @game_id);

SET @room_id = LAST_INSERT_ID();

-- ==============================
-- 3. Crear 3 Jugadores
-- ==============================
INSERT INTO player (name, avatar_src, birthdate, id_room, is_host, `order`) VALUES
('t_detective1', '/avatars/avatar1.jpg', '1996-05-05', @room_id, TRUE, 1),
('t_detective2', '/avatars/avatar2.jpg', '1997-06-06', @room_id, FALSE, 2),
('t_detective3', '/avatars/avatar3.jpg', '1998-07-07', @room_id, FALSE, 3);

SET @player1_id = LAST_INSERT_ID();
SET @player2_id = @player1_id + 1;
SET @player3_id = @player1_id + 2;

-- ==============================
-- 4. Actualizar player_turn_id en Game
-- ==============================
UPDATE game SET player_turn_id = @player1_id WHERE id = @game_id;

-- ==============================
-- 5. Crear Turn activo
-- ==============================
INSERT INTO turn (number, id_game, player_id, status, start_time) 
VALUES (1, @game_id, @player1_id, 'IN_PROGRESS', CURRENT_TIMESTAMP);

SET @turn_id = LAST_INSERT_ID();

-- ==============================
-- 6. Repartir SECRETOS (3 por jugador)
-- ==============================

-- t_detective1: 3 secretos genéricos
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(@game_id, 3, 'SECRET_SET', 1, @player1_id, TRUE),
(@game_id, 3, 'SECRET_SET', 2, @player1_id, TRUE),
(@game_id, 3, 'SECRET_SET', 3, @player1_id, TRUE);

-- t_detective2: Murderer + 2 secretos genéricos
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(@game_id, 2, 'SECRET_SET', 1, @player2_id, TRUE),
(@game_id, 3, 'SECRET_SET', 2, @player2_id, TRUE),
(@game_id, 3, 'SECRET_SET', 3, @player2_id, TRUE);

-- t_detective3: Accomplice + 2 secretos genéricos
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(@game_id, 3, 'SECRET_SET', 1, @player3_id, TRUE),
(@game_id, 1, 'SECRET_SET', 2, @player3_id, TRUE),
(@game_id, 3, 'SECRET_SET', 3, @player3_id, TRUE);

-- ==============================
-- 7. Repartir MANOS (6 cartas por jugador)
-- ==============================

-- t_detective1: 2 Miss Marple + 1 Harley Quin + otras (PUEDE BAJAR SET!)
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(@game_id, 6, 'HAND', 1, @player1_id, TRUE),   -- Miss Marple
(@game_id, 6, 'HAND', 2, @player1_id, TRUE),   -- Miss Marple
(@game_id, 4, 'HAND', 3, @player1_id, TRUE),   -- Harley Quin (comodín)
(@game_id, 15, 'HAND', 4, @player1_id, TRUE),  -- Social Faux Pas (devious)
(@game_id, 13, 'HAND', 5, @player1_id, TRUE),  -- Not so fast (instant)
(@game_id, 17, 'HAND', 6, @player1_id, TRUE);  -- Point suspicions (event)

-- t_detective2: Cartas mixtas
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(@game_id, 7, 'HAND', 1, @player2_id, TRUE),   -- Parker Pyne
(@game_id, 7, 'HAND', 2, @player2_id, TRUE),   -- Parker Pyne
(@game_id, 11, 'HAND', 3, @player2_id, TRUE),  -- Hercule Poirot
(@game_id, 13, 'HAND', 4, @player2_id, TRUE),  -- Not so fast
(@game_id, 14, 'HAND', 5, @player2_id, TRUE),  -- Blackmailed
(@game_id, 15, 'HAND', 6, @player2_id, TRUE);  -- Social Faux Pas

-- t_detective3: Cartas mixtas
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(@game_id, 12, 'HAND', 1, @player3_id, TRUE),  -- Satterthwaite
(@game_id, 4, 'HAND', 2, @player3_id, TRUE),   -- Harley Quin
(@game_id, 7, 'HAND', 3, @player3_id, TRUE),   -- Parker Pyne
(@game_id, 22, 'HAND', 4, @player3_id, TRUE),  -- Early train (event)
(@game_id, 23, 'HAND', 5, @player3_id, TRUE),  -- Cards off table (event)
(@game_id, 13, 'HAND', 6, @player3_id, TRUE);  -- Not so fast

-- ==============================
-- 8. Distribuir cartas restantes en DRAFT (3 cartas visibles)
-- ==============================
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(@game_id, 8, 'DRAFT', 1, NULL, FALSE),   -- Tommy Beresford
(@game_id, 12, 'DRAFT', 2, NULL, FALSE),  -- Mr Satterthwaite
(@game_id, 16, 'DRAFT', 3, NULL, FALSE);  -- Delay escape (event)

-- ==============================
-- 9. Distribuir cartas restantes en DISCARD (algunas ya descartadas)
-- ==============================
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(@game_id, 13, 'DISCARD', 1, NULL, FALSE),  -- Not so fast (visible)
(@game_id, 18, 'DISCARD', 2, NULL, FALSE),  -- Dead card folly (event, visible en tope)
(@game_id, 19, 'DISCARD', 3, NULL, FALSE);  -- Another victim (event, tope del mazo)

-- ==============================
-- 10. Resto de cartas en DECK (mazo de robar)
-- ==============================
-- Cartas detective restantes
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(@game_id, 4, 'DECK', 1, NULL, TRUE),   -- Harley Quin
(@game_id, 4, 'DECK', 2, NULL, TRUE),   -- Harley Quin
(@game_id, 4, 'DECK', 3, NULL, TRUE),   -- Harley Quin
(@game_id, 5, 'DECK', 4, NULL, TRUE),   -- Adriane Oliver
(@game_id, 5, 'DECK', 5, NULL, TRUE),   -- Adriane Oliver
(@game_id, 5, 'DECK', 6, NULL, TRUE),   -- Adriane Oliver
(@game_id, 6, 'DECK', 7, NULL, TRUE),   -- Miss Marple
(@game_id, 7, 'DECK', 8, NULL, TRUE),   -- Parker Pyne
(@game_id, 7, 'DECK', 9, NULL, TRUE),   -- Parker Pyne
(@game_id, 8, 'DECK', 10, NULL, TRUE),  -- Tommy Beresford
(@game_id, 9, 'DECK', 11, NULL, TRUE),  -- Lady Eileen Brent
(@game_id, 9, 'DECK', 12, NULL, TRUE),  -- Lady Eileen Brent
(@game_id, 10, 'DECK', 13, NULL, TRUE), -- Tuppence Beresford
(@game_id, 11, 'DECK', 14, NULL, TRUE), -- Hercule Poirot
(@game_id, 11, 'DECK', 15, NULL, TRUE), -- Hercule Poirot
(@game_id, 12, 'DECK', 16, NULL, TRUE); -- Mr Satterthwaite

-- Cartas instant restantes
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(@game_id, 13, 'DECK', 17, NULL, TRUE),  -- Not so fast
(@game_id, 13, 'DECK', 18, NULL, TRUE),  -- Not so fast
(@game_id, 13, 'DECK', 19, NULL, TRUE),  -- Not so fast
(@game_id, 13, 'DECK', 20, NULL, TRUE);  -- Not so fast

-- Cartas devious restantes
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(@game_id, 15, 'DECK', 21, NULL, TRUE);  -- Social Faux Pas

-- Cartas event restantes
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES
(@game_id, 16, 'DECK', 22, NULL, TRUE),  -- Delay escape
(@game_id, 16, 'DECK', 23, NULL, TRUE),  -- Delay escape
(@game_id, 17, 'DECK', 24, NULL, TRUE),  -- Point suspicions
(@game_id, 17, 'DECK', 25, NULL, TRUE),  -- Point suspicions
(@game_id, 20, 'DECK', 26, NULL, TRUE),  -- Look into ashes
(@game_id, 20, 'DECK', 27, NULL, TRUE),  -- Look into ashes
(@game_id, 21, 'DECK', 28, NULL, TRUE),  -- Card trade
(@game_id, 21, 'DECK', 29, NULL, TRUE),  -- Card trade
(@game_id, 22, 'DECK', 30, NULL, TRUE),  -- Early train
(@game_id, 23, 'DECK', 31, NULL, TRUE),  -- Cards off table
(@game_id, 24, 'DECK', 32, NULL, TRUE),  -- Murder Escapes! (última carta)
(@game_id, 18, 'DECK', 33, NULL, TRUE);  -- Dead card folly

-- ==============================
-- RESUMEN DE DATOS CREADOS
-- ==============================
-- Game ID: @game_id (probablemente 2)
-- Room ID: @room_id (probablemente 4)
-- Player 1 (t_detective1): @player1_id (probablemente 6) - ES SU TURNO
-- Player 2 (t_detective2): @player2_id (probablemente 7)
-- Player 3 (t_detective3): @player3_id (probablemente 8)
-- Turn ID: @turn_id (probablemente 1)
--
-- t_detective1 puede bajar: 2 Miss Marple + 1 Harley Quin = Set válido!
-- ==============================

SELECT 
    CONCAT('✅ Game creado con ID: ', @game_id) AS status
UNION ALL
SELECT CONCAT('✅ Room creado con ID: ', @room_id)
UNION ALL
SELECT CONCAT('✅ Player 1 (t_detective1) ID: ', @player1_id, ' - ES SU TURNO')
UNION ALL
SELECT CONCAT('✅ Player 2 (t_detective2) ID: ', @player2_id)
UNION ALL
SELECT CONCAT('✅ Player 3 (t_detective3) ID: ', @player3_id)
UNION ALL
SELECT CONCAT('✅ Turn activo ID: ', @turn_id)
UNION ALL
SELECT '✅ Cartas repartidas: 3 secretos + 6 mano por jugador'
UNION ALL
SELECT '✅ t_detective1 tiene set válido de Miss Marple (2 cartas + 1 comodín)';

USE cards_table_develop;

-- Limpiar datos existentes
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE cardsXgame;
TRUNCATE TABLE player;
TRUNCATE TABLE room;
TRUNCATE TABLE game;
TRUNCATE TABLE card;
SET FOREIGN_KEY_CHECKS = 1;

-- ==============================
-- Insert Cards
-- ==============================
INSERT INTO card (name, description, type, img_src, qty) VALUES
-- Secret Cards
('You are the Accomplice!', 'If the Murderer escapes, you both win the game, even if this secret card is revealed! However, if the Murderer is revealed, you both lose the game.', 'SECRET', '/cards/secret_accomplice.png', 1),
('You are the Murderer!!', 'If this card is revealed, you are caught and have lost the game. If the Murder Escapes! card is revealed, you get away with murder and win the game!', 'SECRET', '/cards/secret_murderer.png', 1),
('Secret Card', 'A mysterious secret', 'SECRET', '/cards/secret_front.png', 16),

-- Detective Cards
('Harley Quin Wildcard', 'Play in conjunction with any original detective card to play a set in front of you.', 'DETECTIVE', '/cards/detective_quin.png', 4),
('Adriane Oliver', 'Add to any existing set on the table. The player owning the set must reveal a secret card of their choice. May only be added, and not played as a set.', 'DETECTIVE', '/cards/detective_oliver.png', 3),
('Miss Marple', 'Choose a player, who must reveal a secret card of your choice', 'DETECTIVE', '/cards/detective_marple.png', 3),
('Parker Pyne', 'Instead of revealing a secret card, flip any face-up secret card face-down. This may remove social disgrace.', 'DETECTIVE', '/cards/detective_pyne.png', 3),
('Tommy Beresford', 'Choose a player, who must reveal a secret card of their choice. If a Tommy and a Tuppence are in the same set, the action cannot be cancelled by a "Not so Fast" card.', 'DETECTIVE', '/cards/detective_tommyberesford.png', 2),
('Lady Eileen "Bundle" Brent', 'Choose a player who mus reveal a secret card of their choice. If cancelled by a "Not so fast..." card, return the detective set to your hand', 'DETECTIVE', '/cards/detective_brent.png', 3),
('Tuppence Beresford', 'Choose a player, who must reveal a secret card of their choice. If a Tuppence and a Tommy are in the same set, the action cannot be cancelled by a "Not so Fast" card.', 'DETECTIVE', '/cards/detective_tuppenceberesford.png', 2),
('Hercule Poirot', 'Choose a player, who must reveal a secret card of your choice', 'DETECTIVE', '/cards/detective_poirot.png', 3),
('Mr Satterthwaite', 'Choose a player, who must reveal a secret card of their choice. If this set is played with a Harley Quin Wildcard, add the revealed secret card, face-down, to your secrets.', 'DETECTIVE', '/cards/detective_satterthwaite.png', 2),

-- Instant Cards
('Not so fast', 'Play this card at any time, even if it is not your turn. It cancels an action before it is taken, unless otherwise stated, including cancelling another "Not so fast..." card.', 'INSTANT', '/cards/instant_notsofast.png', 10),

-- Devious Cards
('Blackmailed', 'If you have received this card from another player, you must show them one secret card of their choice, before returning it face-down to your secrets. Cannot be cancelled by NSF. This card can only be used during a Card Trade or a Dead Card Folly.', 'DEVIUOS', '/cards/devious_blackmailed.png', 1),
('Social Faux Pas', 'If you have received this card from another player, you must reveal a secret card of your choice. This card can only be used during a Card Trade or a Dead Card Folly.', 'DEVIUOS', '/cards/devious_fauxpas.png', 3),

-- Event Cards
('Delay the murderers escape!', 'Take up to five cards from the top of the discard pile and place them face-down on the draw pile in any order, then remove this card from the game.', 'EVENT', '/cards/event_delayescape.png', 3),
('Point your suspicions', 'All players must point at the person they suspect as the Murderer. The active player breaks ties. The mos suspected player must reveal a secret card of their choice.', 'EVENT', '/cards/event_pointsuspicions.png', 3),
('Dead card folly', 'All players must pass one card from their hand, face-down, to the player on their right or left. The active player decides which direction.', 'EVENT', '/cards/event_deadcardfolly.png', 3),
('Another Victim', 'Take any existing set from another player and play it in front of you. You now own this set.', 'EVENT', '/cards/event_anothervictim.png', 2),
('Look into the ashes', 'You may look though the top five cards of the discard pile and take one into your hand', 'EVENT', '/cards/event_lookashes.png', 3),
('Card trade', 'Choose another player and exchange one card from your hand with them. They cannot refuse. You may ask for a card of your choice, but beware you may be tricked.', 'EVENT', '/cards/event_cardtrade.png', 3),
('And then there was one more...', 'Choose one revealed secret card and add it, face-down, to any players secrets, including your own. This may remove social disgrace.', 'EVENT', '/cards/event_onemore.png', 2),
('Early train to paddington', 'Take the top six cards from the draw pile and place them face-up on the discard pile, then remove this card from the game. Discarding this card is treated the same as if you had played it.', 'EVENT', '/cards/event_earlytrain.png', 2),
('Cards off the table', 'Choose a player, who must discard all the "Not so fast..." cards in their hand. The action cannot be cancelled by a "Not so fast..." card.', 'EVENT', '/cards/event_cardsonthetable.png', 1),

-- Endgame Card
('Murderer Escapes!', 'Having evaded all your efforts to unmask them, the murderer escapes into the shadows! The murderer wins the game.', 'END', '/cards/murder_escapes.png', 1);

-- ==============================
-- Create Games
-- ==============================
INSERT INTO game (id, player_turn_id) VALUES
(1, NULL);

-- ==============================
-- Create Rooms
-- ==============================
INSERT INTO room (name, players_min, players_max, password, status, id_game) VALUES
('Waiting Room 1', 2, 6, NULL, 'WAITING', NULL),
('Waiting Room 2', 2, 6, NULL, 'WAITING', NULL),
('Active Room', 2, 3, NULL, 'INGAME', 1);

-- ==============================
-- Create Players
-- ==============================
INSERT INTO player (name, avatar_src, birthdate, id_room, is_host, `order`) VALUES
('Host1', '/avatars/avatar1.jpg', '1992-05-01', 1, TRUE, 1),
('Host2', '/avatars/avatar2.jpg', '1995-07-12', 2, TRUE, 1),
('Guest2', '/avatars/avatar3.jpg', '2000-09-21', 2, FALSE, 2),
('DetectiveA', '/avatars/avatar4.jpg', '1991-06-20', 3, TRUE, 1),
('DetectiveB', '/avatars/avatar5.jpg', '2002-08-14', 3, FALSE, 2);

-- ==============================
-- CardsXGame Initial Setup
-- ==============================

-- Player 4 (DetectiveA) Hand
INSERT INTO cardsXgame (id_game, id_card, is_in, position, player_id, hidden) VALUES

(1, 14, 'HAND', 1, 4, true), -- NSF obligatoria
(1, 4, 'HAND', 2, 4, true),  -- Harley Quin
(1, 8, 'HAND', 3, 4, true),  -- Parker Pyne
(1, 17, 'HAND', 4, 4, true), -- Point suspicions
(1, 21, 'HAND', 5, 4, true), -- Card trade
(1, 15, 'HAND', 6, 4, true), -- Social Faux Pas

-- Player 4 Secrets 
(1, 2, 'SECRET_SET', 1, 4, true),  -- Murderer
(1, 3, 'SECRET_SET', 2, 4, true),  -- Generic Secret
(1, 3, 'SECRET_SET', 3, 4, true),  -- Generic Secret

-- Player 5 (DetectiveB) Hand:
(1, 14, 'HAND', 1, 5, true),  -- NSF
(1, 5, 'HAND', 2, 5, true),  -- Miss Marple
(1, 9, 'HAND', 3, 5, true),  -- Tommy Beresford
(1, 18, 'HAND', 4, 5, true), -- Dead card folly
(1, 20, 'HAND', 5, 5, true), -- Look into ashes
(1, 22, 'HAND', 6, 5, true), -- Early train

-- Player 5 Secrets 
(1, 3, 'SECRET_SET', 1, 5, true),  -- Generic Secret
(1, 3, 'SECRET_SET', 2, 5, true),  -- Generic Secret
(1, 3, 'SECRET_SET', 3, 5, true),  -- Generic Secret

-- DRAFT 
(1, 6, 'DRAFT', 1, NULL, false),  -- Lady Brent
(1, 10, 'DRAFT', 2, NULL, false), -- Hercule Poirot
(1, 19, 'DRAFT', 3, NULL, false), -- Another Victim

-- DISCARD 
(1, 14, 'DISCARD', 1, NULL, false), -- NSF en el tope (visible)
(1, 7, 'DISCARD', 2, NULL, true),   -- Tuppence oculta
(1, 16, 'DISCARD', 3, NULL, true),  -- Delay escape oculta

-- DECK (resto de cartas, Murderer Escapes al final)
(1, 14, 'DECK', 1, NULL, true),  -- NSF
(1, 11, 'DECK', 2, NULL, true),  -- Mr Satterthwaite
(1, 14, 'DECK', 3, NULL, true),  -- NSF
(1, 14, 'DECK', 4, NULL, true),  -- NSF
(1, 15, 'DECK', 5, NULL, true),  -- Social Faux Pas
(1, 17, 'DECK', 6, NULL, true),  -- Point suspicions
(1, 20, 'DECK', 7, NULL, true),  -- Look into ashes
(1, 23, 'DECK', 8, NULL, true)  -- Murderer Escapes (última carta)
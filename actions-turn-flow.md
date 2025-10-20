# Database Flow Documentation - Murder Mystery Game

## Table of Contents
1. [Detective Cards Flow](#detective-cards-flow)
2. [Discard and Draw Actions](#discard-and-draw-actions)
3. [Instant Cards (Not so Fast)](#instant-cards-not-so-fast)
4. [Event Cards Flow](#event-cards-flow)
5. [Devious Cards Flow](#devious-cards-flow)

---

## Detective Cards Flow

### ESCENARIO 1: Miss Marple (3 cartas iguales) | Poirot tiene mismo efecto

**Jugador 2 baja 3 Miss Marple y elige que Jugador 4 revele su secreto #5**

#### Registros en `CardsXGame` (actualización)
```sql
-- Las 3 cartas pasan de HAND a DETECTIVE_SET
UPDATE cardsXgame SET 
  is_in = 'DETECTIVE_SET',
  position = 1,  -- Todas tienen position=1 porque pertenecen al mismo set
  hidden = FALSE
WHERE id IN (101, 102, 103);  -- IDs de las 3 Miss Marple en la mano del jugador
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Bajar el set
{
  id: 501,
  id_game: 10,
  turn_id: 25,
  player_id: 2,  # Quien baja el set
  action_type: 'DETECTIVE_SET',
  action_name: 'Miss Marple',
  result: 'SUCCESS',
  parent_action_id: NULL,
  triggered_by_action_id: NULL,
  # resto NULL
}

# Action 2 (HIJA): Carta 1 del set
{
  id: 502,
  id_game: 10,
  turn_id: 25,
  player_id: 2,
  action_type: 'DETECTIVE_SET',
  selected_card_id: 101,  # Primera Miss Marple
  result: 'SUCCESS',
  parent_action_id: 501,  # Pertenece al set padre
  # resto NULL
}

# Action 3 (HIJA): Carta 2 del set
{
  id: 503,
  id_game: 10,
  turn_id: 25,
  player_id: 2,
  action_type: 'DETECTIVE_SET',
  selected_card_id: 102,  # Segunda Miss Marple
  result: 'SUCCESS',
  parent_action_id: 501,
  # resto NULL
}

# Action 4 (HIJA): Carta 3 del set
{
  id: 504,
  id_game: 10,
  turn_id: 25,
  player_id: 2,
  action_type: 'DETECTIVE_SET',
  selected_card_id: 103,  # Tercera Miss Marple
  result: 'SUCCESS',
  parent_action_id: 501,
  # resto NULL
}

# Action 5 (CONSECUENCIA): Efecto del detective - Revelar secreto
{
  id: 505,
  id_game: 10,
  turn_id: 25,
  player_id: 2,  # Quien ejecuta la acción
  action_type: 'REVEAL_SECRET',
  action_name: 'Miss Marple Effect',
  player_target: 4,  # Jugador que debe revelar
  secret_target: 205,  # ID del CardsXGame del secreto #5
  result: 'SUCCESS',
  parent_action_id: 501,  # Es consecuencia del set
  # resto NULL
}
```

#### Registros en `CardsXGame` (actualización del secreto revelado)
```sql
UPDATE cardsXgame SET 
  hidden = FALSE  -- El secreto ahora es visible
WHERE id = 205;
```

---

### ESCENARIO 2: Hercule Poirot (1 carta + Harley Quin)

**Jugador 1 baja 1 Poirot + 1 Harley Quin y elige que Jugador 3 revele su secreto #8**

#### Registros en `CardsXGame`
```sql
UPDATE cardsXgame SET 
  is_in = 'DETECTIVE_SET',
  position = 2,  -- Nuevo set, position=2
  hidden = FALSE
WHERE id IN (110, 111);  -- Poirot + Harley Quin
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Bajar el set
{
  id: 601,
  id_game: 10,
  turn_id: 26,
  player_id: 1,
  action_type: 'DETECTIVE_SET',
  action_name: 'Hercule Poirot + Wildcard',
  result: 'SUCCESS',
  parent_action_id: NULL,
}

# Action 2 (HIJA): Poirot
{
  id: 602,
  player_id: 1,
  action_type: 'DETECTIVE_SET',
  selected_card_id: 110,
  parent_action_id: 601,
}

# Action 3 (HIJA): Harley Quin
{
  id: 603,
  player_id: 1,
  action_type: 'DETECTIVE_SET',
  selected_card_id: 111,
  parent_action_id: 601,
}

# Action 4 (CONSECUENCIA): Efecto - Revelar secreto elegido por quien baja
{
  id: 604,
  player_id: 1,
  action_type: 'REVEAL_SECRET',
  action_name: 'Hercule Poirot Effect',
  player_target: 3,
  secret_target: 208,  # Secreto #8 elegido por jugador 1
  parent_action_id: 601,
  result: 'SUCCESS',
}
```

```sql
UPDATE cardsXgame SET hidden = FALSE WHERE id = 208;
```

---

### ESCENARIO 3: Tommy + Tuppence Beresford

**Jugador 3 baja 1 Tommy + 1 Tuppence, elige que Jugador 1 revele secreto. Jugador 1 intenta cancelar con "Not so Fast" pero NO PUEDE**

#### Registros en `CardsXGame`
```sql
UPDATE cardsXgame SET 
  is_in = 'DETECTIVE_SET',
  position = 3,
  hidden = FALSE
WHERE id IN (120, 121);  -- Tommy + Tuppence
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Set Tommy + Tuppence
{
  id: 701,
  id_game: 10,
  turn_id: 27,
  player_id: 3,
  action_type: 'DETECTIVE_SET',
  action_name: 'Tommy + Tuppence Beresford',
  result: 'SUCCESS',
  parent_action_id: NULL,
}

# Action 2, 3 (HIJAS): Cartas del set
{
  id: 702,
  player_id: 3,
  action_type: 'DETECTIVE_SET',
  selected_card_id: 120,  # Tommy
  parent_action_id: 701,
}
{
  id: 703,
  player_id: 3,
  action_type: 'DETECTIVE_SET',
  selected_card_id: 121,  # Tuppence
  parent_action_id: 701,
}

# Action 4 (INTENTO DE CANCELACIÓN): Jugador 1 juega "Not so Fast"
{
  id: 704,
  id_game: 10,
  turn_id: 27,
  player_id: 1,  # Quien intenta cancelar
  action_type: 'INSTANT',
  action_name: 'Not so Fast',
  selected_card_id: 150,  # La carta "Not so Fast" jugada
  parent_action_id: 701,  # Intenta cancelar el set
  result: 'FAILED',  # FALLA porque Tommy+Tuppence no se puede cancelar
}

# Action 5 (CONSECUENCIA): Efecto - Revelar secreto (se ejecuta igual)
{
  id: 705,
  player_id: 3,
  action_type: 'REVEAL_SECRET',
  action_name: 'Tommy/Tuppence Effect',
  player_target: 1,
  secret_target: 201,
  parent_action_id: 701,
  result: 'SUCCESS',
}
```

```sql
-- La carta "Not so Fast" va al descarte pero no tuvo efecto
UPDATE cardsXgame SET is_in = 'DISCARD' WHERE id = 150;

-- El secreto se revela igual
UPDATE cardsXgame SET hidden = FALSE WHERE id = 201;
```

---

### ESCENARIO 4: Mr Satterthwaite + Harley Quin (efecto especial)

**Jugador 2 baja 1 Satterthwaite + 1 Harley Quin, hace que Jugador 4 revele secreto #7, y ADEMÁS se queda con ese secreto face-down**

#### Registros en `CardsXGame`
```sql
UPDATE cardsXgame SET 
  is_in = 'DETECTIVE_SET',
  position = 4,
  hidden = FALSE
WHERE id IN (130, 131);  -- Satterthwaite + Harley
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Set
{
  id: 801,
  player_id: 2,
  action_type: 'DETECTIVE_SET',
  action_name: 'Mr Satterthwaite + Wildcard',
  result: 'SUCCESS',
}

# Action 2, 3: Cartas del set
{id: 802, selected_card_id: 130, parent_action_id: 801}
{id: 803, selected_card_id: 131, parent_action_id: 801}

# Action 4: Revelar secreto
{
  id: 804,
  action_type: 'REVEAL_SECRET',
  player_target: 4,
  secret_target: 207,
  parent_action_id: 801,
}

# Action 5: Efecto especial - Robar el secreto revelado
{
  id: 805,
  player_id: 2,
  action_type: 'MOVE_CARD',
  action_name: 'Satterthwaite Special Effect',
  selected_card_id: 207,  # El secreto revelado
  player_source: 4,  # De quien era
  player_target: 2,  # A quien va (jugador 2)
  to_be_hidden: TRUE,  # Se agrega face-down
  parent_action_id: 801,
}
```

#### Registros en `CardsXGame` (actualización compleja)
```sql
-- Primero se revela
UPDATE cardsXgame SET hidden = FALSE WHERE id = 207;

-- Luego se oculta de nuevo y cambia de dueño
UPDATE cardsXgame SET 
  player_id = 2,  -- Ahora pertenece al jugador 2
  is_in = 'SECRET_SET',
  hidden = TRUE,  -- Face-down en los secretos del jugador 2
  position = 5  -- Nueva posición en los secretos de jugador 2
WHERE id = 207;
```

---

### ESCENARIO 5: Ariadne Oliver (agregar a set existente)

**Jugador 4 agrega Ariadne Oliver al set position=1 de Jugador 2 (las 3 Miss Marple). Jugador 2 debe revelar un secreto de su elección**

#### Registros en `CardsXGame`
```sql
UPDATE cardsXgame SET 
  is_in = 'DETECTIVE_SET',
  position = 1,  -- Se agrega al set existente (mismo position)
  player_id = 2,  -- Ahora pertenece al dueño del set
  hidden = FALSE
WHERE id = 140;  -- Ariadne Oliver
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Agregar detective a set existente
{
  id: 901,
  id_game: 10,
  turn_id: 28,
  player_id: 4,  # Quien agrega la carta
  action_type: 'ADD_DETECTIVE',
  action_name: 'Ariadne Oliver',
  selected_card_id: 140,  # La Ariadne Oliver
  selected_set_id: 1,  # Se agrega al set position=1
  player_target: 2,  # Dueño del set
  result: 'SUCCESS',
}

# Action 2: Efecto - El dueño del set revela secreto de SU elección
{
  id: 902,
  player_id: 2,  # El dueño del set ejecuta
  action_type: 'REVEAL_SECRET',
  action_name: 'Ariadne Oliver Effect',
  player_source: 2,  # Revela su propio secreto
  secret_target: 203,  # Secreto que elige revelar
  parent_action_id: 901,
}
```

```sql
UPDATE cardsXgame SET hidden = FALSE WHERE id = 203;
```

---

### ESCENARIO 6: Parker Pyne (ocultar secreto)

**Jugador 1 baja 2 Parker Pyne y decide OCULTAR el secreto #5 que estaba revelado**

#### Registros en `CardsXGame`
```sql
UPDATE cardsXgame SET 
  is_in = 'DETECTIVE_SET',
  position = 5,
  hidden = FALSE
WHERE id IN (145, 146);  -- 2 Parker Pyne
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Set Parker Pyne
{
  id: 1001,
  player_id: 1,
  action_type: 'DETECTIVE_SET',
  action_name: 'Parker Pyne',
  result: 'SUCCESS',
}

# Action 2, 3: Cartas
{id: 1002, selected_card_id: 145, parent_action_id: 1001}
{id: 1003, selected_card_id: 146, parent_action_id: 1001}

# Action 4: Efecto - OCULTAR secreto en vez de revelar
{
  id: 1004,
  player_id: 1,
  action_type: 'HIDE_SECRET',
  action_name: 'Parker Pyne Effect',
  secret_target: 205,  # Secreto que estaba revelado
  to_be_hidden: TRUE,
  parent_action_id: 1001,
}
```

```sql
UPDATE cardsXgame SET hidden = TRUE WHERE id = 205;
```

---

### ESCENARIO 7: Lady Eileen Bundle Brent (cancelado y devuelto)

**Jugador 3 baja 2 Bundle Brent, Jugador 2 cancela con "Not so Fast", las cartas vuelven a la mano de Jugador 3**

#### Registros en `CardsXGame` (primero van al set, luego vuelven)
```sql
-- Primero se bajan
UPDATE cardsXgame SET 
  is_in = 'DETECTIVE_SET',
  position = 6,
  hidden = FALSE
WHERE id IN (155, 156);
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Intentar bajar set
{
  id: 1101,
  player_id: 3,
  action_type: 'DETECTIVE_SET',
  action_name: 'Lady Eileen Bundle Brent',
  result: 'CANCELLED',  #  Terminará cancelado
}

# Action 2, 3: Cartas
{id: 1102, selected_card_id: 155, parent_action_id: 1101}
{id: 1103, selected_card_id: 156, parent_action_id: 1101}

# Action 4: Cancelación exitosa
{
  id: 1104,
  player_id: 2,
  action_type: 'INSTANT',
  action_name: 'Not so Fast',
  selected_card_id: 160,
  parent_action_id: 1101,
  result: 'SUCCESS',  # Cancela exitosamente
}
```

#### Registros en `CardsXGame` (rollback)
```sql
-- Las cartas vuelven a la mano (efecto especial de Bundle Brent)
UPDATE cardsXgame SET 
  is_in = 'HAND',
  position = 1, --2
  hidden = TRUE,
  player_id = 3
WHERE id IN (155); --156

-- La carta "Not so Fast" va al descarte
UPDATE cardsXgame SET is_in = 'DISCARD' WHERE id = 160;
```

---

### RESUMEN DE PATTERNS - Detective Cards

| Detective | Mínimo Set | Registros `ActionsPerTurn` | Notas Especiales |
|-----------|-----------|---------------------------|------------------|
| **Miss Marple** | 3 iguales o 1+wildcard | 1 padre + N cartas + 1 reveal (elegido por quien baja) | - |
| **Hercule Poirot** | 3 iguales o 1+wildcard | 1 padre + N cartas + 1 reveal (elegido por quien baja) | - |
| **Mr Satterthwaite** | 2 iguales o 1+wildcard | 1 padre + N cartas + 1 reveal + 1 move (si hay wildcard) | Efecto especial: roba el secreto |
| **Parker Pyne** | 2 iguales o 1+wildcard | 1 padre + N cartas + 1 hide | Oculta en vez de revelar |
| **Tommy Beresford** | 2 iguales, 1+Tuppence, o 1+wildcard | 1 padre + N cartas + 1 reveal | No cancelable si está con Tuppence |
| **Tuppence Beresford** | 2 iguales, 1+Tommy, o 1+wildcard | 1 padre + N cartas + 1 reveal | No cancelable si está con Tommy |
| **Bundle Brent** | 2 iguales o 1+wildcard | 1 padre + N cartas + (1 reveal o rollback) | Si se cancela, cartas vuelven a mano |
| **Ariadne Oliver** | Solo agregar | 1 add + 1 reveal (dueño elige) | No forma set propio |
| **Harley Quin** | Solo con otros | Parte de otro set | Es wildcard |

---

## Discard and Draw Actions

### ESCENARIO 1: Descartar cartas al final del turno

**Jugador 2 termina su turno con 6 cartas en mano, descarta 3 cartas para quedarse con 6 antes de recoger**

#### Registros en `CardsXGame`
```sql
-- Las 3 cartas pasan de HAND a DISCARD
UPDATE cardsXgame SET 
  is_in = 'DISCARD',
  position = 15,  -- Nueva posición en el discard pile (top = mayor número)
  hidden = FALSE  -- Las cartas en discard están visibles
WHERE id = 301;   -- Primera carta descartada

UPDATE cardsXgame SET 
  is_in = 'DISCARD',
  position = 16,
  hidden = FALSE
WHERE id = 302;  -- Segunda carta

UPDATE cardsXgame SET 
  is_in = 'DISCARD',
  position = 17,
  hidden = FALSE
WHERE id = 303;  -- Tercera carta
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Acción de descarte múltiple
{
  id: 2001,
  id_game: 10,
  turn_id: 30,
  player_id: 2,
  action_type: 'DISCARD',
  action_name: 'End Turn Discard',
  result: 'SUCCESS',
  parent_action_id: NULL,
}

# Action 2 (HIJA): Primera carta descartada
{
  id: 2002,
  id_game: 10,
  turn_id: 30,
  player_id: 2,
  action_type: 'DISCARD',
  selected_card_id: 301,
  position_card: 15,  # Posición en discard pile
  parent_action_id: 2001,
  result: 'SUCCESS',
}

# Action 3 (HIJA): Segunda carta
{
  id: 2003,
  player_id: 2,
  action_type: 'DISCARD',
  selected_card_id: 302,
  position_card: 16,
  parent_action_id: 2001,
  result: 'SUCCESS',
}

# Action 4 (HIJA): Tercera carta
{
  id: 2004,
  player_id: 2,
  action_type: 'DISCARD',
  selected_card_id: 303,
  position_card: 17,
  parent_action_id: 2001,
  result: 'SUCCESS',
}
```

---

### ESCENARIO 2: Recoger del mazo común (DRAW_PILE)

**Jugador 2 recoge 3 cartas del mazo para completar su mano**

#### Registros en `CardsXGame`
```sql
-- Las 6 cartas pasan de DECK a HAND
UPDATE cardsXgame SET 
  is_in = 'HAND',
  player_id = 2,
  hidden = TRUE,  -- En la mano están ocultas para otros
  position = 4    -- 5, 6
WHERE id IN (401); --402, 403 
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Recoger cartas
{
  id: 2101,
  id_game: 10,
  turn_id: 30,
  player_id: 2,
  action_type: 'DRAW',
  action_name: 'Draw from Deck',
  source_pile: 'DRAW_PILE',
  result: 'SUCCESS',
  parent_action_id: NULL,
}

# Action 2-7 (HIJAS): Cada carta recogida
{
  id: 2102,
  player_id: 2,
  action_type: 'DRAW',
  selected_card_id: 401,
  source_pile: 'DRAW_PILE',
  parent_action_id: 2101,
}
{
  id: 2103,
  player_id: 2,
  action_type: 'DRAW',
  selected_card_id: 402,
  source_pile: 'DRAW_PILE',
  parent_action_id: 2101,
}
# ... (2104 con carta 403)
```

---

### ESCENARIO 3: Recoger del DRAFT (SELECT_PILE)

**Al finalizar turno, Jugador 1 recoge 1 cartas del draft pile**

#### Registros en `CardsXGame`
```sql
UPDATE cardsXgame SET 
  is_in = 'HAND',
  player_id = 1,
  hidden = TRUE,
  position = 6
WHERE id IN (501);
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Recoger del draft
{
  id: 2201,
  id_game: 10,
  turn_id: 1,  # Primer turno
  player_id: 1,
  action_type: 'DRAW',
  action_name: 'Draft Phase',
  source_pile: 'SELECT_PILE',
  result: 'SUCCESS',
}

# Action 2-7: Cada carta del draft
{
  id: 2202,
  player_id: 1,
  action_type: 'DRAW',
  selected_card_id: 501,
  source_pile: 'SELECT_PILE',
  parent_action_id: 2201,
}

```

---

### ESCENARIO 4: Recoger del DISCARD_PILE

**Jugador 3 usa evento "Look into the ashes" - mira top 5 del discard y toma 1**

#### Registros en `CardsXGame`
```sql
-- Primero juega la carta de evento (pasa a DISCARD)
UPDATE cardsXgame SET 
  is_in = 'DISCARD',
  position = 20,
  hidden = FALSE
WHERE id = 600;  -- La carta "Look into the ashes"

-- Luego toma una carta del discard pile a su mano
UPDATE cardsXgame SET 
  is_in = 'HAND',
  player_id = 3,
  hidden = TRUE,
  position = 2
WHERE id = 315;  -- Carta elegida del top 5 del discard
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Jugar evento
{
  id: 2301,
  id_game: 10,
  turn_id: 31,
  player_id: 3,
  action_type: 'EVENT_CARD',
  action_name: 'Look into the ashes',
  selected_card_id: 600,
  result: 'SUCCESS',
}

# Action 2: Recoger carta del discard
{
  id: 2302,
  player_id: 3,
  action_type: 'DRAW',
  selected_card_id: 315,
  source_pile: 'DISCARD_PILE',
  position_card: 18,  # Estaba en posición 18 del discard
  parent_action_id: 2301,  # Consecuencia del evento
  result: 'SUCCESS',
}
```

---

### ESCENARIO 8: Descartar y recoger en EL MISMO TURNO

**Jugador 1 descarta 4 cartas y luego recoge 6 (reponiendo hasta tener 6 en mano)**

#### Registros en `CardsXGame`
```sql
-- Descartar 4
UPDATE cardsXgame SET is_in = 'DISCARD', position = 26, hidden = FALSE WHERE id = 1001;
UPDATE cardsXgame SET is_in = 'DISCARD', position = 27, hidden = FALSE WHERE id = 1002;
UPDATE cardsXgame SET is_in = 'DISCARD', position = 28, hidden = FALSE WHERE id = 1003;
UPDATE cardsXgame SET is_in = 'DISCARD', position = 29, hidden = FALSE WHERE id = 1004;

-- Recoger 6 del draw pile
UPDATE cardsXgame SET is_in = 'HAND', player_id = 1, hidden = TRUE WHERE id IN (1101, 1102, 1103, 1104, 1105, 1106);
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Descarte
{
  id: 2701,
  turn_id: 35,
  player_id: 1,
  action_type: 'DISCARD',
  action_name: 'End Turn Discard',
}

# Action 2-5: Cartas descartadas
{id: 2702, selected_card_id: 1001, position_card: 26, parent_action_id: 2701}
{id: 2703, selected_card_id: 1002, position_card: 27, parent_action_id: 2701}
{id: 2704, selected_card_id: 1003, position_card: 28, parent_action_id: 2701}
{id: 2705, selected_card_id: 1004, position_card: 29, parent_action_id: 2701}

# Action 6 (PADRE): Recoger
{
  id: 2706,
  turn_id: 35,
  player_id: 1,
  action_type: 'DRAW',
  source_pile: 'DRAW_PILE',
  parent_action_id: NULL,  # NO es hijo del discard, es acción separada
}

# Action 7-12: Cartas recogidas
{id: 2707, selected_card_id: 1101, source_pile: 'DRAW_PILE', parent_action_id: 2706}
{id: 2708, selected_card_id: 1102, source_pile: 'DRAW_PILE', parent_action_id: 2706}
# ... (2709-2712 con cartas 1103-1106)
```

---

## Instant Cards (Not so Fast)

### ESCENARIO 5: "Not so Fast" - Cancelar acción en TU turno

**Jugador 1 intenta bajar un set de detectives, Jugador 2 juega "Not so Fast" para cancelarlo**

#### Registros en `CardsXGame`
```sql
-- Primero las cartas del set intentan bajarse
UPDATE cardsXgame SET 
  is_in = 'DETECTIVE_SET',
  position = 7,
  hidden = FALSE
WHERE id IN (701, 702);  -- 2 Parker Pyne

-- Luego la carta "Not so Fast" va al descarte
UPDATE cardsXgame SET 
  is_in = 'DISCARD',
  position = 21,
  hidden = FALSE
WHERE id = 750;  -- "Not so Fast" de Jugador 2

-- ROLLBACK: Las cartas vuelven a la mano de Jugador 1
UPDATE cardsXgame SET 
  is_in = 'HAND',
  position = 0,
  hidden = TRUE,
  player_id = 1
WHERE id IN (701, 702);
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Intento de bajar set
{
  id: 2401,
  id_game: 10,
  turn_id: 32,
  player_id: 1,
  action_type: 'DETECTIVE_SET',
  action_name: 'Parker Pyne',
  result: 'CANCELLED',  #  Será cancelado
}

# Action 2, 3: Cartas del set
{
  id: 2402,
  player_id: 1,
  action_type: 'DETECTIVE_SET',
  selected_card_id: 701,
  parent_action_id: 2401,
  result: 'CANCELLED',
}
{
  id: 2403,
  player_id: 1,
  action_type: 'DETECTIVE_SET',
  selected_card_id: 702,
  parent_action_id: 2401,
  result: 'CANCELLED',
}

# Action 4: "Not so Fast" cancela la acción
{
  id: 2404,
  id_game: 10,
  turn_id: 32,  # MISMO TURNO (jugada fuera de turno)
  player_id: 2,  # Jugador 2 lo juega aunque no es su turno
  action_type: 'INSTANT',
  action_name: 'Not so Fast',
  selected_card_id: 750,
  parent_action_id: 2401,  # Cancela esta acción específica
  result: 'SUCCESS',  # ✅ Cancela exitosamente
}
```

---

### ESCENARIO 6: "Not so Fast" cancelando otro "Not so Fast"

**Jugador 1 baja set → Jugador 2 intenta cancelar con NSF → Jugador 3 cancela ESE NSF con otro NSF → El set se ejecuta**

#### Registros en `CardsXGame`
```sql
-- Set se baja exitosamente
UPDATE cardsXgame SET 
  is_in = 'DETECTIVE_SET',
  position = 8,
  hidden = FALSE
WHERE id IN (801, 802, 803);  -- 3 Miss Marple

-- Primera NSF va al descarte (fue cancelada)
UPDATE cardsXgame SET 
  is_in = 'DISCARD',
  position = 22,
  hidden = FALSE
WHERE id = 850;  -- NSF de Jugador 2

-- Segunda NSF va al descarte
UPDATE cardsXgame SET 
  is_in = 'DISCARD',
  position = 23,
  hidden = FALSE
WHERE id = 851;  -- NSF de Jugador 3

-- El secreto se revela (efecto del set)
UPDATE cardsXgame SET hidden = FALSE WHERE id = 210;
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Bajar set exitosamente
{
  id: 2501,
  id_game: 10,
  turn_id: 33,
  player_id: 1,
  action_type: 'DETECTIVE_SET',
  action_name: 'Miss Marple',
  result: 'SUCCESS',  # Al final tiene éxito
}

# Action 2-4: Cartas del set
{id: 2502, selected_card_id: 801, parent_action_id: 2501}
{id: 2503, selected_card_id: 802, parent_action_id: 2501}
{id: 2504, selected_card_id: 803, parent_action_id: 2501}

# Action 5: Primer "Not so Fast" (intenta cancelar)
{
  id: 2505,
  player_id: 2,
  action_type: 'INSTANT',
  action_name: 'Not so Fast',
  selected_card_id: 850,
  parent_action_id: 2501,  # Intenta cancelar el set
  result: 'CANCELLED',  #  Este NSF será cancelado
}

# Action 6: Segundo "Not so Fast" (cancela el primer NSF)
{
  id: 2506,
  player_id: 3,
  action_type: 'INSTANT',
  action_name: 'Not so Fast',
  selected_card_id: 851,
  parent_action_id: 2505,  # Cancela el NSF anterior
  result: 'SUCCESS',  #  Cancela exitosamente
}

# Action 7: Efecto del set se ejecuta
{
  id: 2507,
  player_id: 1,
  action_type: 'REVEAL_SECRET',
  action_name: 'Miss Marple Effect',
  player_target: 4,
  secret_target: 210,
  parent_action_id: 2501,
  result: 'SUCCESS',
}
```

---

### ESCENARIO 7: "Not so Fast" en turno de OTRO jugador (evento)

**Jugador 2 juega evento "Point your suspicions", Jugador 4 cancela con NSF**

#### Registros en `CardsXGame`
```sql
-- Evento intenta jugarse pero va al descarte
UPDATE cardsXgame SET 
  is_in = 'DISCARD',
  position = 24,
  hidden = FALSE
WHERE id = 900;  -- "Point your suspicions"

-- NSF va al descarte
UPDATE cardsXgame SET 
  is_in = 'DISCARD',
  position = 25,
  hidden = FALSE
WHERE id = 950;
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Intento de jugar evento
{
  id: 2601,
  id_game: 10,
  turn_id: 34,
  player_id: 2,
  action_type: 'EVENT_CARD',
  action_name: 'Point your suspicions',
  selected_card_id: 900,
  result: 'CANCELLED',
}

# Action 2: NSF cancela
{
  id: 2602,
  player_id: 4,
  action_type: 'INSTANT',
  action_name: 'Not so Fast',
  selected_card_id: 950,
  parent_action_id: 2601,
  result: 'SUCCESS',
}

# NO hay actions de votar porque fue cancelado
```

---

## RESUMEN DE PATTERNS

### Discard and Draw

| Acción | `action_type` | `source_pile` | Registros en `ActionsPerTurn` | Notas |
|--------|--------------|---------------|-------------------------------|-------|
| **Descartar cartas** | `DISCARD` | NULL | 1 padre + N hijos (1 por carta) | `position_card` = nueva posición en discard |
| **Recoger del mazo** | `DRAW` | `DRAW_PILE` | 1 padre + N hijos | Cartas van de `DECK` a `HAND` |
| **Recoger del draft** | `DRAW` | `SELECT_PILE` | 1 padre + N hijos | Cartas van de `DRAFT` a `HAND` |
| **Recoger del discard** | `DRAW` | `DISCARD_PILE` | 1 padre + N hijos | `position_card` = posición original en discard |

### Instant Cards (Not so Fast)

| Acción | `action_type` | Registros | Notas |
|--------|--------------|-----------|-------|
| **Not so Fast (cancelar)** | `INSTANT` | 1 registro con `parent_action_id` = acción cancelada | Marca acción padre como `result='CANCELLED'` |
| **NSF fuera de turno** | `INSTANT` | Mismo `turn_id` pero diferente `player_id` | Indica que se jugó en turno ajeno |
| **NSF cancela NSF** | `INSTANT` | `parent_action_id` apunta al NSF anterior | Chain de cancelaciones |

---

## REGLAS CLAVE

1. **Descartar siempre actualiza `position`** en el discard pile (secuencial, top = mayor número)
2. **Recoger siempre especifica `source_pile`**
3. **"Not so Fast" usa `parent_action_id`** para referenciar qué acción cancela
4. **Cancelaciones actualizan `result` a `CANCELLED`** en la acción padre
5. **NSF fuera de turno** tiene `turn_id` del turno activo pero `player_id` diferente
6. **Cartas en HAND** tienen `hidden=TRUE`, en DISCARD tienen `hidden=FALSE`
7. **Acciones padre e hijas** se vinculan mediante `parent_action_id`
8. **Cada carta individual** que se mueve genera su propia action hija
9. **Rollbacks** (como Bundle Brent cancelado) requieren UPDATE adicionales devolviendo cartas a su estado original

---

## Event Cards Flow

### ESCENARIO 1: Card Trade (intercambio simple)

**Jugador 1 juega "Card Trade" y pide intercambiar con Jugador 3. Jugador 1 da carta #401, Jugador 3 da carta #402**

#### Registros en `CardsXGame`
```sql
-- La carta de evento va al descarte
UPDATE cardsXgame SET 
  is_in = 'DISCARD',
  position = 30,
  hidden = FALSE
WHERE id = 1200;  -- "Card Trade"

-- Intercambio de cartas (cambian de dueño)
UPDATE cardsXgame SET 
  player_id = 3,
  is_in = 'HAND',
  hidden = TRUE
WHERE id = 401;  -- Carta que era de Jugador 1, ahora de Jugador 3

UPDATE cardsXgame SET 
  player_id = 1,
  is_in = 'HAND',
  hidden = TRUE
WHERE id = 402;  -- Carta que era de Jugador 3, ahora de Jugador 1
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Jugar evento Card Trade
{
  id: 3001,
  id_game: 10,
  turn_id: 40,
  player_id: 1,
  action_type: 'EVENT_CARD',
  action_name: 'Card Trade',
  selected_card_id: 1200,
  player_target: 3,  # Con quién se intercambia
  result: 'SUCCESS',
}

# Action 2: Intercambio de cartas
{
  id: 3002,
  player_id: 1,
  action_type: 'CARD_EXCHANGE',
  card_given_id: 401,  # Carta que da Jugador 1
  card_received_id: 402,  # Carta que recibe Jugador 1
  player_source: 1,  # Quien da
  player_target: 3,  # Quien recibe
  parent_action_id: 3001,
  result: 'SUCCESS',
}
```

---

### ESCENARIO 2: Card Trade + Blackmailed (devious)

**Jugador 1 usa "Card Trade" con Jugador 2. Jugador 2 le pasa "Blackmailed". Jugador 1 debe mostrar un secreto que Jugador 2 elija, luego lo oculta de nuevo**

#### Registros en `CardsXGame`
```sql
-- Evento va al descarte
UPDATE cardsXgame SET is_in = 'DISCARD', position = 31, hidden = FALSE WHERE id = 1201;

-- Intercambio
UPDATE cardsXgame SET player_id = 2, is_in = 'HAND' WHERE id = 405;  -- Carta normal de J1 a J2
UPDATE cardsXgame SET player_id = 1, is_in = 'HAND' WHERE id = 1250;  -- "Blackmailed" de J2 a J1

-- El secreto se revela temporalmente
UPDATE cardsXgame SET hidden = FALSE WHERE id = 210;  -- Secreto elegido por J2

-- Luego se oculta de nuevo
UPDATE cardsXgame SET hidden = TRUE WHERE id = 210;

-- "Blackmailed" se descarta después de usarse
UPDATE cardsXgame SET is_in = 'DISCARD', position = 32, hidden = FALSE WHERE id = 1250;
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Jugar Card Trade
{
  id: 3101,
  turn_id: 41,
  player_id: 1,
  action_type: 'EVENT_CARD',
  action_name: 'Card Trade',
  selected_card_id: 1201,
  player_target: 2,
  result: 'SUCCESS',
}

# Action 2: Intercambio
{
  id: 3102,
  action_type: 'CARD_EXCHANGE',
  card_given_id: 405,
  card_received_id: 1250,  # Recibe "Blackmailed"
  player_source: 1,
  player_target: 2,
  parent_action_id: 3101,
}

# Action 3: Efecto de "Blackmailed" (se activa automáticamente)
{
  id: 3103,
  player_id: 1,  # Quien tiene que revelar
  action_type: 'REVEAL_SECRET',
  action_name: 'Blackmailed Effect',
  secret_target: 210,  # Secreto elegido por J2
  player_target: 2,  # A quien se le muestra
  triggered_by_action_id: 3102,  # Activado por el intercambio
  result: 'SUCCESS',
}

# Action 4: Ocultar el secreto de nuevo
{
  id: 3104,
  player_id: 1,
  action_type: 'HIDE_SECRET',
  secret_target: 210,
  to_be_hidden: TRUE,
  parent_action_id: 3103,  # Parte del efecto de Blackmailed
}
```

---

### ESCENARIO 3: Dead Card Folly (todos pasan carta a la izquierda)

**Jugador 2 juega "Dead Card Folly" y decide dirección LEFT. Hay 4 jugadores: J1→J4, J2→J1, J3→J2, J4→J3**

#### Registros en `CardsXGame`
```sql
-- Evento va al descarte
UPDATE cardsXgame SET is_in = 'DISCARD', position = 33, hidden = FALSE WHERE id = 1300;

-- Cada carta cambia de dueño
UPDATE cardsXgame SET player_id = 4, position = X WHERE id = 501;  -- J1 da a J4 (izquierda)
UPDATE cardsXgame SET player_id = 1, position = X WHERE id = 502;  -- J2 da a J1
UPDATE cardsXgame SET player_id = 2, position = X WHERE id = 503;  -- J3 da a J2
UPDATE cardsXgame SET player_id = 3, position = X WHERE id = 504;  -- J4 da a J3
```

#### Registros en `ActionsPerTurn`
```python
# Action 1 (PADRE): Jugar evento
{
  id: 3201,
  turn_id: 42,
  player_id: 2,
  action_type: 'EVENT_CARD',
  action_name: 'Dead Card Folly',
  selected_card_id: 1300,
  direction: 'LEFT',
  result: 'SUCCESS',
}

# Action 2: J1 pasa carta a J4
{
  id: 3202,
  action_type: 'CARD_EXCHANGE',
  player_source: 1,
  player_target: 4,
  card_given_id: 501,
  direction: 'LEFT',
  parent_action_id: 3201,
}

# Action 3: J2 pasa carta a J1
{
  id: 3203,
  action_type: 'CARD_EXCHANGE',
  player_source: 2,
  player_target: 1,
  card_given_id: 502,
  direction: 'LEFT',
  parent_action_id: 3201,
}

# Action 4: J3 pasa carta a J2
{
  id: 3204,
  action_type: 'CARD_EXCHANGE',
  player_source: 3,
  player_target: 2,
  card_given_id: 503,
  direction: 'LEFT',
  parent_action_id: 3201,
}

# Action 5: J4 pasa carta a J3
{
  id: 3205,
  action_type: 'CARD_EXCHANGE',
  player_source: 4,
  player_target: 3,
  card_given_id: 504,
  direction: 'LEFT',
  parent_action_id: 3201,
}
```

---

### ESCENARIO 4: Dead Card Folly + Social Faux Pas (devious)

**Jugador 3 juega "Dead Card Folly" dirección RIGHT. Jugador 1 recibe "Social Faux Pas" de Jugador 4 y debe revelar un secreto de SU elección**

#### Registros en `CardsXGame`
```sql
-- Evento
UPDATE cardsXgame SET is_in = 'DISCARD', position = 34, hidden = FALSE WHERE id = 1301;

-- Intercambios (dirección RIGHT)
UPDATE cardsXgame SET player_id = 2, position = X WHERE id = 601;  -- J1 da a J2
UPDATE cardsXgame SET player_id = 3, position = X WHERE id = 602;  -- J2 da a J3
UPDATE cardsXgame SET player_id = 4, position = X WHERE id = 603;  -- J3 da a J4
UPDATE cardsXgame SET player_id = 1, position = X WHERE id = 1350;  -- J4 da "Social Faux Pas" a J1

-- Secreto se revela
UPDATE cardsXgame SET hidden = FALSE WHERE id = 215;  -- Secreto de J1

-- "Social Faux Pas" se descarta
UPDATE cardsXgame SET is_in = 'DISCARD', position = 35, hidden = FALSE WHERE id = 1350;
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Evento Dead Card Folly
{
  id: 3301,
  turn_id: 43,
  player_id: 3,
  action_type: 'EVENT_CARD',
  action_name: 'Dead Card Folly',
  direction: 'RIGHT',
}

# Action 2-5: Intercambios de todos los jugadores
{id: 3302, player_source: 1, player_target: 2, card_given_id: 601, parent_action_id: 3301}
{id: 3303, player_source: 2, player_target: 3, card_given_id: 602, parent_action_id: 3301}
{id: 3304, player_source: 3, player_target: 4, card_given_id: 603, parent_action_id: 3301}
{id: 3305, player_source: 4, player_target: 1, card_given_id: 1350, parent_action_id: 3301}

# Action 6: Efecto de "Social Faux Pas"
{
  id: 3306,
  player_id: 1,  # Quien revela
  action_type: 'REVEAL_SECRET',
  action_name: 'Social Faux Pas Effect',
  secret_target: 215,  # Secreto que J1 ELIGE revelar
  triggered_by_action_id: 3305,  # Activado por recibir la carta
}
```

---

### ESCENARIO 5: Point Your Suspicions

**Jugador 2 juega "Point your suspicions". Jugadores votan: J1→J3, J2→J3, J3→J1, J4→J3. Jugador 3 es el más sospechoso (3 votos) y revela un secreto**

#### Registros en `CardsXGame`
```sql
-- Evento al descarte
UPDATE cardsXgame SET is_in = 'DISCARD', position = 36, hidden = FALSE WHERE id = 1400;

-- Secreto revelado
UPDATE cardsXgame SET hidden = FALSE WHERE id = 220;
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Jugar evento
{
  id: 3401,
  turn_id: 44,
  player_id: 2,
  action_type: 'EVENT_CARD',
  action_name: 'Point Your Suspicions',
  selected_card_id: 1400,
}

# Action 2-5: Votos de cada jugador
{
  id: 3402,
  action_type: 'VOTE',
  player_source: 1,  # Quien vota
  player_target: 3,  # A quién vota
  parent_action_id: 3401,
}
{
  id: 3403,
  action_type: 'VOTE',
  player_source: 2,
  player_target: 3,
  parent_action_id: 3401,
}
{
  id: 3404,
  action_type: 'VOTE',
  player_source: 3,
  player_target: 1,
  parent_action_id: 3401,
}
{
  id: 3405,
  action_type: 'VOTE',
  player_source: 4,
  player_target: 3,
  parent_action_id: 3401,
}

# Action 6: Jugador más votado revela secreto
{
  id: 3406,
  player_id: 3,  # El más sospechoso
  action_type: 'REVEAL_SECRET',
  action_name: 'Point Your Suspicions Effect',
  secret_target: 220,  # Secreto que J3 ELIGE revelar
  parent_action_id: 3401,
}
```

---

### ESCENARIO 6: Another Victim (robar set completo)

**Jugador 4 juega "Another Victim" y roba el set position=2 de Jugador 1 (2 Hercule Poirot + 1 Harley Quin)**

#### Registros en `CardsXGame`
```sql
-- Evento al descarte
UPDATE cardsXgame SET is_in = 'DISCARD', position = 37, hidden = FALSE WHERE id = 1500;

-- Las cartas del set cambian de dueño (siguen en DETECTIVE_SET, mismo position)
UPDATE cardsXgame SET 
  player_id = 4  -- Ahora pertenecen a J4
WHERE id IN (110, 111, 112) AND position = 2;
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Jugar evento
{
  id: 3501,
  turn_id: 45,
  player_id: 4,
  action_type: 'EVENT_CARD',
  action_name: 'Another Victim',
  selected_card_id: 1500,
  player_target: 1,  # De quién se roba
  selected_set_id: 2,  # El set position=2
}

# Action 2: Robar el set (acción de robo)
{
  id: 3502,
  action_type: 'STEAL_SET',
  player_source: 1,  # Dueño original
  player_target: 4,  # Nuevo dueño
  selected_set_id: 2,
  parent_action_id: 3501,
}

# Action 3-5: Cada carta que se roba (opcional, para tracking detallado)
{id: 3503, action_type: 'MOVE_CARD', selected_card_id: 110, parent_action_id: 3502}
{id: 3504, action_type: 'MOVE_CARD', selected_card_id: 111, parent_action_id: 3502}
{id: 3505, action_type: 'MOVE_CARD', selected_card_id: 112, parent_action_id: 3502}
```

---

### ESCENARIO 7: Look Into the Ashes

**Jugador 3 juega "Look into the ashes", mira top 5 del discard (positions 33-37) y toma la carta en position 35**

_(Este ya lo cubrimos en la sección de DRAW, pero lo repito para completitud)_

#### Registros en `CardsXGame`
```sql
UPDATE cardsXgame SET is_in = 'DISCARD', position = 38, hidden = FALSE WHERE id = 1600;
UPDATE cardsXgame SET is_in = 'HAND', player_id = 3, hidden = TRUE WHERE id = 335;
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Jugar evento
{
  id: 3601,
  turn_id: 46,
  player_id: 3,
  action_type: 'EVENT_CARD',
  action_name: 'Look Into the Ashes',
  selected_card_id: 1600,
}

# Action 2: Tomar carta del discard
{
  id: 3602,
  action_type: 'DRAW',
  selected_card_id: 335,
  source_pile: 'DISCARD_PILE',
  position_card: 35,
  parent_action_id: 3601,
}
```

---

### ESCENARIO 8: And Then There Was One More...

**Jugador 1 juega "And then there was one more...", toma el secreto revelado #220 de Jugador 3 y lo agrega face-down a los secretos de Jugador 4**

#### Registros en `CardsXGame`
```sql
-- Evento
UPDATE cardsXgame SET is_in = 'DISCARD', position = 39, hidden = FALSE WHERE id = 1700;

-- El secreto cambia de dueño y se oculta
UPDATE cardsXgame SET 
  player_id = 4,  -- Nuevo dueño
  is_in = 'SECRET_SET',
  hidden = TRUE,  -- Face-down
  position = 8  -- Nueva posición en secretos de J4
WHERE id = 220;
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Jugar evento
{
  id: 3701,
  turn_id: 47,
  player_id: 1,
  action_type: 'EVENT_CARD',
  action_name: 'And Then There Was One More',
  selected_card_id: 1700,
  player_target: 4,  # A quién se le agrega el secreto
}

# Action 2: Mover secreto
{
  id: 3702,
  action_type: 'MOVE_CARD',
  selected_card_id: 220,  # El secreto revelado
  player_source: 3,  # De quien era
  player_target: 4,  # A quien va
  to_be_hidden: TRUE,  # Se agrega face-down
  parent_action_id: 3701,
}
```

---

### ESCENARIO 9: Delay the Murderers Escape

**Jugador 2 juega "Delay the murderers escape", toma 5 cartas del top del discard (positions 35-39) y las coloca en el draw pile en orden específico: [39, 37, 35, 36, 38]**

#### Registros en `CardsXGame`
```sql
-- Evento se REMUEVE del juego (no va a discard)
UPDATE cardsXgame SET 
  is_in = 'REMOVED',
  position = 0
WHERE id = 1800;

-- Las 5 cartas pasan de DISCARD a DECK
UPDATE cardsXgame SET is_in = 'DECK', position = 100 WHERE id = 339;  -- Primera en draw pile
UPDATE cardsXgame SET is_in = 'DECK', position = 101 WHERE id = 337;
UPDATE cardsXgame SET is_in = 'DECK', position = 102 WHERE id = 335;
UPDATE cardsXgame SET is_in = 'DECK', position = 103 WHERE id = 336;
UPDATE cardsXgame SET is_in = 'DECK', position = 104 WHERE id = 338;  -- Última (top del draw)
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Jugar evento
{
  id: 3801,
  turn_id: 48,
  player_id: 2,
  action_type: 'EVENT_CARD',
  action_name: 'Delay the Murderers Escape',
  selected_card_id: 1800,
}

# Action 2-6: Cada carta que se mueve (en orden de colocación)
{
  id: 3802,
  action_type: 'MOVE_CARD',
  selected_card_id: 339,
  source_pile: 'DISCARD_PILE',
  position_card: 100,  # Nueva posición en draw pile
  parent_action_id: 3801,
}
{
  id: 3803,
  action_type: 'MOVE_CARD',
  selected_card_id: 337,
  position_card: 101,
  parent_action_id: 3801,
}
# ... (3804, 3805, 3806 para cartas 335, 336, 338)
```

---

### ESCENARIO 10: Early Train to Paddington

**Jugador 3 descarta "Early train to paddington" (o lo juega). Top 6 cartas del draw pile van al discard face-up**

#### Registros en `CardsXGame`
```sql
-- Evento se REMUEVE del juego
UPDATE cardsXgame SET is_in = 'REMOVED' WHERE id = 1900;

-- Top 6 del draw pile pasan a discard
UPDATE cardsXgame SET is_in = 'DISCARD', position = 40, hidden = FALSE WHERE id = 701;
UPDATE cardsXgame SET is_in = 'DISCARD', position = 41, hidden = FALSE WHERE id = 702;
UPDATE cardsXgame SET is_in = 'DISCARD', position = 42, hidden = FALSE WHERE id = 703;
UPDATE cardsXgame SET is_in = 'DISCARD', position = 43, hidden = FALSE WHERE id = 704;
UPDATE cardsXgame SET is_in = 'DISCARD', position = 44, hidden = FALSE WHERE id = 705;
UPDATE cardsXgame SET is_in = 'DISCARD', position = 45, hidden = FALSE WHERE id = 706;
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Jugar/Descartar evento
{
  id: 3901,
  turn_id: 49,
  player_id: 3,
  action_type: 'EVENT_CARD',  # O 'DISCARD' si se descarta
  action_name: 'Early Train to Paddington',
  selected_card_id: 1900,
}

# Action 2-7: Cada carta que se mueve del draw al discard
{id: 3902, action_type: 'MOVE_CARD', selected_card_id: 701, position_card: 40, parent_action_id: 3901}
{id: 3903, action_type: 'MOVE_CARD', selected_card_id: 702, position_card: 41, parent_action_id: 3901}
# ... (3904-3907 para cartas 703-706)
```

---

### ESCENARIO 11: Cards Off the Table

**Jugador 1 juega "Cards off the table", elige a Jugador 4 quien tiene 3 "Not so Fast" en mano. Las 3 NSF se descartan. Esta acción NO PUEDE ser cancelada por NSF**

#### Registros en `CardsXGame`
```sql
-- Evento al descarte
UPDATE cardsXgame SET is_in = 'DISCARD', position = 46, hidden = FALSE WHERE id = 2000;

-- Las 3 NSF de J4 se descartan
UPDATE cardsXgame SET is_in = 'DISCARD', position = 47, hidden = FALSE WHERE id = 801;
UPDATE cardsXgame SET is_in = 'DISCARD', position = 48, hidden = FALSE WHERE id = 802;
UPDATE cardsXgame SET is_in = 'DISCARD', position = 49, hidden = FALSE WHERE id = 803;
```

#### Registros en `ActionsPerTurn`
```python
# Action 1: Jugar evento
{
  id: 4001,
  turn_id: 50,
  player_id: 1,
  action_type: 'EVENT_CARD',
  action_name: 'Cards Off the Table',
  selected_card_id: 2000,
  player_target: 4,  # Quien debe descartar sus NSF
  result: 'SUCCESS',
}

# Action 2: Descartar todas las NSF (acción forzada)
{
  id: 4002,
  action_type: 'DISCARD',
  player_id: 4,
  parent_action_id: 4001,
}

# Action 3-5: Cada NSF descartada
{id: 4003, action_type: 'DISCARD', selected_card_id: 801, position_card: 47, parent_action_id: 4002}
{id: 4004, action_type: 'DISCARD', selected_card_id: 802, position_card: 48, parent_action_id: 4002}
{id: 4005, action_type: 'DISCARD', selected_card_id: 803, position_card: 49, parent_action_id: 4002}

# SI alguien intenta jugar NSF para cancelar:
# Action 6 (FALLIDA):
{
  id: 4006,
  player_id: 2,
  action_type: 'INSTANT',
  action_name: 'Not so Fast',
  selected_card_id: 850,
  parent_action_id: 4001,
  result: 'FAILED',  # No puede cancelar "Cards Off the Table"
}
```

---

## Devious Cards Flow

### ESCENARIO 1: Blackmailed durante Card Trade

_(Ya cubierto en ESCENARIO 2 de Event Cards, pero resumido aquí)_

**Características:**
- Solo se activa durante "Card Trade" o "Dead Card Folly"
- No puede ser cancelado por NSF
- Fuerza al receptor a mostrar un secreto que el DADOR elige
- El secreto se revela y luego se oculta de nuevo
- La carta "Blackmailed" se descarta después de usarse

#### Pattern en `ActionsPerTurn`
```python
# 1. Evento padre (Card Trade o Dead Card Folly)
# 2. Intercambio de cartas (incluye "Blackmailed")
# 3. Reveal secret (triggered_by_action_id apunta al intercambio)
# 4. Hide secret (parent_action_id apunta al reveal)
```

---

### ESCENARIO 2: Social Faux Pas durante Dead Card Folly

_(Ya cubierto en ESCENARIO 4 de Event Cards)_

**Características:**
- Solo se activa durante "Card Trade" o "Dead Card Folly"
- Fuerza al receptor a revelar un secreto de SU PROPIA elección
- El secreto permanece revelado (no se oculta)
- La carta "Social Faux Pas" se descarta después de usarse

#### Pattern en `ActionsPerTurn`
```python
# 1. Evento padre (Card Trade o Dead Card Folly)
# 2. Intercambio de cartas (incluye "Social Faux Pas")
# 3. Reveal secret (triggered_by_action_id apunta al intercambio)
#    - player_id = quien recibió la carta
#    - secret_target = secreto que ELIGE revelar
```

---

## RESUMEN DE PATTERNS - Event Cards

| Event Card | Registros `ActionsPerTurn` | Notas Especiales |
|------------|---------------------------|------------------|
| **Card Trade** | 1 event + 1 exchange | Intercambio 1:1, pueden activar devious cards |
| **Dead Card Folly** | 1 event + N exchanges (1 por jugador) | Todos pasan carta en dirección elegida |
| **Point Your Suspicions** | 1 event + N votes + 1 reveal | Votación grupal, más votado revela |
| **Another Victim** | 1 event + 1 steal_set + N move_card | Roba set completo de otro jugador |
| **Look Into the Ashes** | 1 event + 1 draw | Mira top 5 discard, toma 1 |
| **And Then There Was One More** | 1 event + 1 move_card | Mueve secreto revelado a otro jugador face-down |
| **Delay the Murderers Escape** | 1 event + N move_card (hasta 5) | Mueve cartas de discard a draw, evento se REMUEVE |
| **Early Train to Paddington** | 1 event + 6 move_card | Mueve 6 del draw al discard, evento se REMUEVE |
| **Cards Off the Table** | 1 event + 1 discard + N discard (NSF) | No cancelable por NSF, descarta todas las NSF del target |

---

## RESUMEN DE PATTERNS - Devious Cards

| Devious Card | Activación | Efecto | Puede Cancelarse |
|--------------|-----------|--------|------------------|
| **Blackmailed** | Card Trade o Dead Card Folly | Receptor muestra secreto que DADOR elige, luego se oculta |  NO |
| **Social Faux Pas** | Card Trade o Dead Card Folly | Receptor revela secreto de SU elección, queda revelado |  SI (antes de ser recibida) |

---

## REGLAS ADICIONALES - Event Cards

1. **Cartas removidas del juego**: "Delay the Murderers Escape" y "Early Train to Paddington" usan `is_in = 'REMOVED'`
2. **Cards Off the Table**: No puede ser cancelada por NSF (igual que Tommy+Tuppence, Blackmailed)
3. **Another Victim**: El set robado actualiza su `position` para matchear los sets del nuevo jugador. Además cambia `player_id`
4. **Point Your Suspicions**: Si hay empate, el jugador activo (quien jugó la carta) decide
5. **Devious cards**: Se descartan inmediatamente después de activarse su efecto
6. **triggered_by_action_id**: Se usa cuando una carta devious se activa COMO CONSECUENCIA de un intercambio
7. **Direction**: En "Dead Card Folly" puede ser 'LEFT' (descendentemente) o 'RIGHT' (ascendentemente), determina la dirección del pase
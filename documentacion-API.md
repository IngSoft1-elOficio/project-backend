# API: Cards on the Table - Agatha Christie

> Documento vivo para Sprint 3. Mantener sincronizado con los cambios de backend y front.
> Documentación de la API válido para SPRINT 1, 2 y 3. 
> Para información más confiable, visitar: ttp://localhost:8000/docs con el backend corriendo. 

## 1. Introducción

- **Propósito**: describir la API REST y los eventos de WebSocket del juego
- **Alcance Sprint 1**: Inicio de sesión y lobby. Crear o unirse a una partida. Jugar con manos y secretos asignados. Acciones permitidas: descartar cartas y reponer del mazo. El juego termina al llegar a la última carta del mazo ("murder escapes").
- **Alcance Sprint 2**: Se incorpora la jugabilidad de las cartas de eventos y bajar set de detectives. 
- **Alcance Sprint 2**: Se incorpora la jugabilidad general de las cartas eventos restantes, agregar carta a set propio o ajeno, desgracia social, ganar por revelar al asesino. 
- **Base URL**: http://localhost:8000
- **WebSocket base**: ws://localhost:8000

## 2. Convenciones

- **Formato**: JSON en requests y responses
- **Códigos HTTP**: usar 2xx para éxito, 4xx para errores de cliente, 5xx para servidor
- **Errores**: objeto Error con campos code, message, details
- **CORS**: orígenes permitidos según ALLOWED_ORIGINS
- **WebSocket**: header HTTP_USER_ID en el handshake; rooms con nombre game_{game_id}

## 3. Esquemas comunes

Esta sección refleja los modelos actuales del backend (SQLAlchemy) y agrega "view models" pensados para las respuestas del API.

### 3.1 Enums

- **CardType**: "EVENT" | "SECRET" | "INSTANT" | "DEVIUOS" | "DETECTIVE" | "END"
- **RoomStatus**: "WAITING" | "INGAME" | "FINISH"
- **CardState**: "DECK" | "DRAFT" | "DISCARD" | "SECRET_SET" | "DETECTIVE_SET" | "HAND" | "REMOVED"
- **TurnStatus**: "IN_PROGRESS" | "FINISHED"
- **ActionType**: 
  - "EVENT_CARD" // Jugada de carta de evento
  - "DETECTIVE_SET" // Bajar set de detective
  - "ADD_DETECTIVE" // Agregar detective a set existente
  - "DISCARD" // Descartar cartas
  - "DRAW" // Robar carta
  - "INSTANT" // Carta instantánea
  - "REVEAL_SECRET" // Revelar secreto
  - "HIDE_SECRET" // Ocultar secreto
  - "VOTE" // Votación
  - "CARD_EXCHANGE" // Intercambio de cartas
  - "MOVE_CARD" // Mover carta entre estados
  - "STEAL_SET" // Robar set de detective
- **ActionResult**: "PENDING" | "SUCCESS" | "CANCELLED" | "FAILED"
- **Direction**: "LEFT" | "RIGHT"
- **SourcePile**: "DRAFT_PILE" | "DRAW_PILE" | "DISCARD_PILE"

### 3.2 Entidades persistentes (DB)

**Game**
- id: integer
- player_turn_id: integer | null (FK a Player)

**Room**
- id: integer
- name: string
- players_min: integer (default: 2)
- players_max: integer (default: 6)
- password: string | null
- status: RoomStatus
- id_game: integer (FK a Game)

**Player**
- id: integer
- name: string
- avatar_src: string
- birthdate: date (YYYY-MM-DD)
- id_room: integer (FK a Room)
- is_host: boolean
- order: integer | null

**Card**
- id: integer
- name: string
- description: string
- type: CardType
- img_src: string (URL o ruta)
- qty: integer // Cantidad disponible de cada carta

**CardsXGame**
- id: integer
- id_game: integer (FK a Game)
- id_card: integer (FK a Card)
- is_in: CardState
- position: integer
- player_id: integer | null (FK a Player)
- hidden: boolean (default: true) // Indica si la carta es visible o no

**Turn**
- id: integer
- number: integer
- id_game: integer (FK a Game)
- player_id: integer (FK a Player)
- status: TurnStatus (IN_PROGRESS | FINISHED)
- start_time: datetime (default: CURRENT_TIMESTAMP)

**ActionsPerTurn**
- id: integer
- id_game: integer (FK a Game)
- turn_id: integer (FK a Turn)
- player_id: integer (FK a Player)
- action_time: datetime (default: CURRENT_TIMESTAMP)
- action_name: string(40)
- action_type: ActionType
- result: ActionResult (PENDING | SUCCESS | CANCELLED | FAILED)
- parent_action_id: integer | null (FK a ActionsPerTurn)
- triggered_by_action_id: integer | null (FK a ActionsPerTurn)
- player_source: integer | null (FK a Player)
- player_target: integer | null (FK a Player)
- secret_target: integer | null (FK a CardsXGame)
- selected_card_id: integer | null (FK a CardsXGame)
- card_given_id: integer | null (FK a CardsXGame)
- card_received_id: integer | null (FK a CardsXGame)
- direction: Direction (LEFT | RIGHT)
- source_pile: SourcePile (DRAFT_PILE | DRAW_PILE | DISCARD_PILE)
- position_card: integer | null
- selected_set_id: integer | null
- to_be_hidden: boolean | null

### 3.3 View Models (API)

**ActionResult**
- discarded: CardSummary[]  // cartas que salieron de la mano del solicitante
- drawn: CardSummary[]      // cartas tomadas del mazo regular tras el descarte
- action_type: string       // tipo de acción realizada (ej: "discard", "detective_action", etc)
- action_time: string       // timestamp ISO-8601 de la acción
- source_player_id: integer | null  // jugador que inició la acción
- target_player_id: integer | null  // jugador objetivo si aplica

Para desacoplar la forma de persistencia del contrato público, las respuestas del API exponen objetos agregados:

**GameView**
- id: integer
- name: string
- players_min: integer      // mínimo de jugadores (default: 2)
- players_max: integer      // máximo de jugadores (default: 6)
- status: "waiting" | "in_game" | "finished"  // mapeo desde Room.status
- host_id: integer

**PlayerView**
- id: integer
- name: string
- avatar: string  // mapea avatar_src
- birthdate: string (YYYY-MM-DD)
- is_host: boolean
- order: integer | null

**CardSummary**
- id: integer
- name: string
- type: CardType
- img: string    // mapea a img_src | se utiliza la imagen del canto de carta si no es visible (secretos, mazo)
- qty: integer   // cantidad disponible de esta carta en el juego
- hidden: boolean // indica si la carta es visible o no para otros jugadores

**DeckView**
- remaining: integer  // cantidad de cartas en DECK

**DiscardView**
- top: CardSummary | null  // última carta visible (máximo position en DISCARD)
- count: integer           // cantidad total en DISCARD

**HandView**
- player_id: integer       // dueño de esta mano
- cards: CardSummary[]     // exactamente 6 cartas en HAND

**SecretsView**
- player_id: integer       // dueño de estos secretos
- cards: CardSummary[]     // exactamente 3 cartas en SECRET_SET visibles para su dueño

**TurnInfo**
- current_player_id: integer | null
- order: integer[]  // ids de jugadores en orden de turnos
- can_act: boolean // indica si jugador actual puede realizar acciones

**Notas:**
- El orden de turnos se define al iniciar la partida (POST /game/{room_id}/start) calculando la distancia de cada birthdate al cumpleaños de Agatha Christie; la persona más cercana va primero y el resto en orden ascendente de distancia. Antes de iniciar, order puede estar vacío o no definido.

**GameStateView**
- game: GameView
- players: PlayerView[]
- deck: DeckView
- discard: DiscardView
- hand?: HandView         // sólo para el jugador solicitante
- secrets?: SecretsView   // sólo para el jugador solicitante
- turn: TurnInfo

**Error**
- code: string  // p.ej. "validation_error", "not_found", "conflict"
- message: string
- details: object | null

### 3.4 Mapeos y decisiones

**Identidad pública de la partida**
- La entidad pública inicial es Room. POST /game crea la Room en estado WAITING con id_game = null. Cuando la partida pasa a INGAME, POST /game/{room_id}/start crea Game y setea Room.id_game = Game.id.

**Status público**
- Mapeo desde RoomStatus: WAITING → waiting, INGAME → in_game, FINISH → finished.

**Mazos y descartes**
- Se derivan de CardsXGame: is_in = DECK / DISCARD / DRAFT y position define el orden.
- top_discard es la carta con mayor position en DISCARD (la última descartada y visible).

**Mano, secretos y set de detectives del jugador**
- Mano: CardsXGame con is_in = HAND y player_id = id del jugador.
- Secretos: CardsXGame con is_in = SECRET_SET y player_id = id del jugador.
- Set de detectives: CardsXGame con is_in = DETECTIVE_SET y player_id = id del jugador. Todas las cartas pertenecientes al mismo set bajado tendrán el mismo position. 

**Campos sensibles**
- Solo devolver HandView y SecretsView al propietario. El resto ve counts y top_discard.

**Host**
- El host se identifica por Player.is_host = true. En respuestas agregadas se puede derivar host_id como el id del Player host.

**Enums expuestos por el API**
- Respetan exactamente los enums de la base actual

**Unicidad**
- Room.name es único global. Además, dentro de una partida, (name + avatar_src) es único por jugador.

**Visibilidad de las cartas**
- Se agrega el atributo "hidden" dentro de CardsXGame para indicar si las cartas son visibles en general o no. 

### 3.5 Ejemplos

**PlayerView**
```json
{
    "id": 7,
    "name": "Ana",
    "avatar": "/assets/avatars/detective1.png",
    "birthdate": "2000-05-10",
    "is_host": true,
    "order": 1
}
```


**Presets de avatar**
- Ruta base: /assets/avatars/
- Set permitido: detective1.png … detective8.png
- Ejemplos: /assets/avatars/detective1.png, /assets/avatars/detective8.png

**GameStateView**
```json
{
    "game": {
        "id": 42,
        "name": "Mesa 1",
        "players_min": 2,
        "players_max": 6,
        "status": "waiting",
        "host_id": 7
    },
    "players": [
        {
            "id": 7,
            "name": "Ana",
            "avatar": "/assets/avatars/detective1.png",
            "birthdate": "2000-05-10",
            "is_host": true,
            "order": 1
        }
    ],
    "deck": {
        "remaining": 52
    },
    "discard": {
        "top": null,
        "count": 0
    },
    "draft": {
        "cards": [position=1, cardID=5, ... ]
    }
    "turn": {
        "current_player_id": 7,
        "order": [7,4,5,9],
        "can_act": true
    }
}
```

## 4. Endpoints REST

### 4.1 GET /game_state/{room_id}

**Descripción**: obtener el estado agregado de la partida EN CURSO para una room dada.

**Path params**: 
- room_id: integer

**Comportamiento**
- Si Room.status = "INGAME": devuelve GameStateView
- Si Room.status = "WAITING": 409 "game_not_started"

**Responses**
- 200: GameStateView
- 404: Error (La partida no existe)
- 409: Error { code: "game_not_started", message }

**Ejemplo curl**
```bash
curl -s "http://localhost:8000/game_state/42"
```


**Errores por endpoint**
- 404 not_found: room_id inexistente
- 409 game_not_started: la room está en WAITING
- 500 server_error: error inesperado

**Ejemplo 200**
```json
{
    "game": {"id": 42, "name": "Mesa 1", "players_min": 4, "players_max": 6 , "status": "in_game", "host_id": 7},
    "players": [{"id": 7, "name": "Ana", "avatar": "/assets/avatars/detective1.png", "birthdate": "2000-05-10", "is_host": true, "order": 1}],
    "deck": {"remaining": 37},
    "discard": {"top": {"id": 101, "name": "Not So Fast", "type": "INSTANT"}, "count": 15},
    "hand": {"player_id": 7, "cards": [{"id": 12, "name": "Cards off the table", "type": "EVENT"}]},
    "secrets": {"player_id": 7, "cards": [{"id": 77, "name": "You're the murderer", "type": "SECRET"}]},
    "turn": {"current_player_id": 7, "order": [7, 9, 13, 20], "can_act": true}
}
```


**Ejemplo 409**

```json
{
    "code": "game_not_started",
    "message": "La partida aún no fue iniciada",
    "details": {"room_id": 42}
}
```


### 4.2 POST /game

**Descripción**: crea una sala (Room) en estado WAITING con nombre único y cantidad de jugadores objetivo. Crea además el Player solicitante como is_host=true en esa Room. id_game permanece null hasta iniciar la partida.

**Body**
```json
{
    "name": "Mesa 1",
    "players_min": 2,
    "players_max": 4,
    "player": {
    "name": "Ana",
    "avatar": "/assets/avatars/detective1.png",
    "birthdate": "2000-05-10"
}
```

**Responses**

**201 Created**
```json
{
    "room": { "id": 42, "name": "Mesa 1", "players_min": 2, "players_max": 4, "status": "waiting", "host_id": 7 },
    "players": [
        { "id": 7, "name": "Ana", "avatar": "/assets/avatars/detective1.png", "birthdate": "2000-05-10", "is_host": true }
    ]
}
```

- 400 validation_error
- 409 conflict (name_duplicated)

**Ejemplo curl**
```bash
curl -s -X POST "http://localhost:8000/game" \
    -H "Content-Type: application/json" \
    -d '{
    "name":"Mesa 1",
    "players_min": 2, 
    "players_max": 4,
    "player":{"name":"Ana","avatar":"/assets/avatars/detective1.png","birthdate":"2000-05-10"}
    }' | jq .
```

**Errores por endpoint**
- 400 validation_error: name vacío o longitud inválida, players_min/players_max inválidos (min: 2, max: 6), player incompleto
- 409 conflict: name_duplicated
- 500 server_error: error inesperado

### 4.3 GET /api/game_list

**Descripción**: lista salas en estado WAITING con cupos disponibles, ordenadas por id (desc).

**Query params opcionales**
- page: number (default 1)
- limit: number (default 20)

**Responses**

**200 OK**
```json
{
    "items": [
        { "id": 42, "name": "Mesa 1", "players_min": 2, "players_max": 4, "players_joined": 1 },
        { "id": 41, "name": "Mesa 0", "players_min": 2, "players_max": 2, "players_joined": 1 }
        ],
    "page": 1,
    "limit": 20
}
```

**Ejemplo curl**

```bash
curl -s "http://localhost:8000/api/game_list?page=1&limit=10"
```

**Errores por endpoint**
- 200 OK (lista vacía si no hay partidas). 
- Usar 500 server_error ante fallas.

### 4.4 POST /game/{room_id}/join

**Descripción**: agrega un jugador a una sala en WAITING con cupo disponible.

**Path params**: 
- room_id: integer

**Body**
```json
{
    "name": "Luis",
    "avatar": "/assets/avatars/detective2.png",
    "birthdate": "1999-03-01"
}
```

**Responses**

**200 OK**
```json
{
    "room": { "id": 42, "name": "Mesa 1", "players_min": 2, "players_max": 4, "status": "waiting" },
    "players": [
        { "id": 7, "name": "Ana", "avatar": "/assets/avatars/detective1.png", "birthdate": "2000-05-10", "is_host": true },
        { "id": 9, "name": "Luis", "avatar": "/assets/avatars/detective2.png", "birthdate": "1999-03-01", "is_host": false }
        ]
}
```

- 404 not_found (room)
- 409 conflict (room_full | name_avatar_taken)

**Ejemplo curl**
```bash
curl -s -X POST "http://localhost:8000/game/42/join" \
    -H "Content-Type: application/json" \
    -d '{"name":"Luis","avatar":"/assets/avatars/detective2.png","birthdate":"1999-03-01"}' | jq .
```


**Errores por endpoint**
- 404 not_found: room inexistente
- 409 conflict: room_full | name_avatar_taken
- 500 server_error: error inesperado

### 4.5 POST /game/{room_id}/start

**Descripción**: iniciar la partida. Crea Game asociado y pasa Room a INGAME.

**Notas**: 
- Al iniciar: 
  - Cada jugador recibe 6 cartas de mano y 3 secretos según reglas del juego
  - Deck.remaining = total_inicial − jugadores×(6+3)
  - Discard.count = 0 y Discard.top = null
  - Turn.order definido según regla de cumpleaños y current_player_id = primer jugador
- Visibilidad: 
  - Hand y Secrets se devuelven solo al dueño
  - Otros jugadores ven counters, cartas boca abajo y discard.top
- Eventos WS emitidos: 
  - game_started { game, turn }
  - hand_updated y secrets_updated por jugador
  - deck_updated y discard counters

**Path params**: 
- room_id: integer

**Comportamiento**
- Crea Game, setea Room.id_game = Game.id
- Cambia Room.status = "INGAME"
- Inicializa mazos y manos y secretos según reglas del juego

**Responses**
- 200: estado inicial de partida en curso (GameStateView)
- 403: no es host
- 409: no cumple condiciones de inicio

**Ejemplo 200**
```json
{
    "game": {"id": 101, "name": "Mesa 1", "players_min": 2, "players_max": 4, "status": "in_game", "host_id": 7},
    "players": [
        {"id": 7, "name": "Ana", "avatar": "/assets/avatars/detective1.png", "birthdate": "2000-05-10", "is_host": true},
        {"id": 9, "name": "Luis", "avatar": "/assets/avatars/detective2.png", "birthdate": "1999-03-01", "is_host": false},
        {"id": 13, "name": "Mia", "avatar": "/assets/avatars/detective3.png", "birthdate": "1998-08-20", "is_host": false},
        {"id": 20, "name": "Sol", "avatar": "/assets/avatars/detective4.png", "birthdate": "2001-11-02", "is_host": false}
    ],
    "deck": {"remaining": 52},
    "discard": {"top": null, "count": 0},
    "hand": {"player_id": 7, "cards": [{"id": 12, "name": "Cards off the table", "type": "EVENT"}, ...]},
    "secrets": {"player_id": 7, "cards": [{"id": 77, "name": "You're the murderer", "type": "SECRET"}, ...]},
    "turn": {"current_player_id": 7, "order": [7, 9, 13, 20], "can_act": true}
}
```

**Ejemplo curl**

```bash
curl -s -X POST "http://localhost:8000/game/42/start"
```


**Errores por endpoint**
- 403 forbidden: quien invoca no es host
- 409 conflict: no cumple condiciones de inicio (mínimo de jugadores, etc.)
- 404 not_found: room_id inexistente
- 500 server_error: error inesperado

### 4.6 POST /game/{room_id}/discard

**Descripción**: descartar N cartas de la mano y reponer desde el mazo regular, finalizando el turno.

**Path params**: 
- room_id: integer

**Headers**:
- HTTP_USER_ID: integer (ID del jugador que realiza la acción)

**Body**
```json
{
    "card_ids": [1, 2, 3]  // Array de IDs de cartas a descartar
}
```

**Responses**

**200 OK**
```json
{
    "action": {
        "discarded": [
            {
                "id": 12,
                "name": "Cards off the table",
                "type": "EVENT",
                "img": "/cards/cards-off-table.png"
            }
        ],
        "drawn": [
            {
                "id": 31,
                "name": "Another victim",
                "type": "EVENT",
                "img": "/cards/another-victim.png"
            }
        ]
    },
    "hand": {
        "player_id": 7,
        "cards": [
            {
                "id": 44,
                "name": "Not so fast",
                "type": "INSTANT",
                "img": "/cards/not-so-fast.png"
            }
        ]
    },
    "deck": {
        "remaining": 36
    },
    "discard": {
        "top": {
            "id": 12,
            "name": "Cards off the table",
            "type": "EVENT",
            "img": "/cards/cards-off-table.png"
        },
        "count": 16
    }
}
```

- 400 validation_error (cartas inválidas, lista vacía)
- 403 forbidden (no es tu turno)
- 404 not_found (room)
- 409 conflict (reglas de descarte no cumplidas)

**Ejemplo curl**

```bash
curl -s -X POST "http://localhost:8000/game/42/discard" \
-H "Content-Type: application/json" \
-d '{"card_ids":[12,31]}' | jq .
```

### 4.7 POST /game/{room_id}/finish-turn

**Descripción**: Finaliza el turno del jugador actual y pasa al siguiente jugador en orden.

**Path params**: 
- room_id: integer

**Body**
```json
{
    "user_id": 7  // ID del jugador que finaliza su turno
}
```

**Comportamiento**
- Valida que sea el turno del jugador solicitante
- Calcula el siguiente jugador según el orden establecido
- Actualiza player_turn_id en la partida
- Emite eventos WebSocket:
  - Notifica el estado actualizado de la partida
  - Notifica que el turno ha finalizado

**Responses**

**200 OK**
```json
{
    "status": "ok",
    "next_turn": 8  // ID del siguiente jugador
}
```

**Errores por endpoint**
- 403 forbidden: no es tu turno (not_your_turn)
- 404 not_found: room_not_found, game_not_found
- 500 server_error: error inesperado

**Eventos WebSocket emitidos**
- notificar_estado_partida: Actualiza el estado completo de la partida
- notificar_turn_finished: Indica que el turno del jugador ha terminado

**Ejemplo curl**
```bash
curl -s -X POST "http://localhost:8000/game/42/finish-turn" \
-H "Content-Type: application/json" \
-d '{"user_id": 7}' | jq .
```

### 4.8 POST /game/{room_id}/draft/pick

**Descripción**: Selecciona una carta del mazo de draft (CardState = DRAFT) para la mano del jugador y repone desde el mazo regular si hay cartas disponibles.

**Path params**: 
- room_id: integer

**Body**
```json
{
    "card_id": 42,
    "position": 2
}
```

**Comportamiento**
- La carta elegida pasa a HAND del jugador ocupando la posición que quedó vacía por la última carta descartada
- Se repone el mazo de draft desde el DECK si hay cartas disponibles
- Si el DECK queda con 1 carta, se activa el final del juego
- Se emiten eventos WebSocket:
  - hand_updated al jugador con la nueva carta en la posición correcta
  - deck_updated y draft_updated al room

**Responses**

**200 OK**
```json
{
    "picked_card": {
        "id": 42,
        "name": "Carta",
        "type": "EVENT",
        "img": "/cards/carta.png"
    },
    "hand": {
        "player_id": 7,
        "cards": [
            {"id": 42, "name": "Carta", "type": "EVENT", "img": "/cards/carta.png"},
            ...
        ]
    },
    "draft": {
        "cards": [
            {"id": 15, "name": "carta1", "type": "EVENT", "img": "//cards/carta.png"},
            {"id": 23, "name": "carta2", "type": "DETECTIVE", "img": "/cards/carta.png"},
            {"id": 31, "name": "carta3", "type": "INSTANT", "img": "/cards/carta.png"}
        ]
    },
    "deck": {
        "remaining": 34
    }
}
```

**Errores por endpoint**
- 403 forbidden: no es el turno del jugador
- 404 not_found: card_id no existe en el mazo de draft (SELECT) de esta partida
- 500 server_error: error inesperado

**Ejemplo curl**
**Ejemplo curl**
```bash
curl -s -X POST "http://localhost:8000/game/42/draft/pick" \
-H "Content-Type: application/json" \
-H "HTTP_USER_ID: 7" \
-d '{"card_id":42, "position":2}' | jq .
```

### 4.9 POST /api/game/{room_id}/play-detective-set

**Descripción**: Jugar un set de cartas de detective, validando la combinación según el tipo de set y gestionando la siguiente acción requerida.

**Nota**: Para entender el flujo completo de acciones y su interacción con la tabla ActionsPerTurn, consultar [actions-turn-flow.md](actions-turn-flow.md)

**Path params**: 
- room_id: integer

**Body**
```json
{
    "owner": "player_id",
    "setType": "poirot",
    "cards": ["card_id1", "card_id2", "card_id3"],
    "hasWildcard": false
}
```

**SetType permitidos**
- "poirot"
- "marple"
- "satterthwaite"
- "eileenbrent"
- "beresford"
- "pyne"

**Comportamiento**
- Valida que las cartas pertenezcan a la mano del jugador
- Verifica que la combinación sea válida para el tipo de set
- Maneja el estado de la acción y determina el siguiente paso
- Emite eventos WebSocket para actualizar el estado del juego

**Responses**

**200 OK**
```json
{
    "success": true,
    "actionId": "action_abc123",
    "nextAction": {
        "type": "selectPlayerAndSecret",
        "allowedPlayers": ["player_id1", "player_id2"],
        "metadata": {
            "hasWildcard": false,
            "secretsPool": "revealed"
        }
    }
}
```

**Tipos de nextAction**
- "selectPlayerAndSecret": Seleccionar jugador y secreto objetivo
- "selectPlayer": Solo seleccionar jugador
- "waitForOpponent": Esperar acción del oponente
- "complete": Acción finalizada

**Errores por endpoint**
- 400 bad_request: cartas inválidas o combinación incorrecta para el tipo de set
- 403 forbidden: no es el turno del jugador o está en desgracia social
- 409 conflict: el estado del juego cambió (concurrencia)
- 500 server_error: error inesperado

**Ejemplo curl**
**Ejemplo curl**
```bash
curl -s -X POST "http://localhost:8000/api/game/42/play-detective-set" \
-H "Content-Type: application/json" \
-H "HTTP_USER_ID: 7" \
-d '{
    "owner": "7",
    "setType": "poirot",
    "cards": ["123", "124", "125"],
    "hasWildcard": false
}' | jq .
```

### 4.10 POST /api/game/{room_id}/detective-action

**Descripción**: Ejecuta la acción siguiente de un set de detective jugado previamente. Las acciones específicas dependen del tipo de set y pueden incluir seleccionar jugador objetivo, elegir secreto y aplicar efectos (revelar, ocultar o transferir).

**Path params**: 
- room_id: integer

**Body**
```json
{
    "actionId": "action_abc123",
    "targetPlayerId": "player_id",  // requerido para selección de jugador
    "secretId": 123                 // requerido para selección de secreto
}
```

**Comportamiento por tipo de set**
- **Poirot/Marple**: 
  - Jugador activo elige jugador y secreto objetivo
  - El secreto queda revelado
- **Satterthwaite**: 
  - Jugador activo elige jugador objetivo
  - Objetivo elige qué secreto propio revelar
  - Si hay comodín: secreto se transfiere al activo boca abajo
- **Eileen Brent**: 
  - Jugador activo elige jugador objetivo
  - Objetivo elige qué secreto propio revelar
- **Hermanos Beresford**: 
  - Jugador activo elige jugador objetivo
  - Objetivo elige qué secreto propio revelar
  - (Tomy/Tuppence cuentan como IDs distintos para el set)
- **Pyne**: 
  - Jugador activo elige jugador objetivo y un secreto revelado
  - El secreto elegido pasa a oculto

**Responses**

**200 OK**
```json
{
    "success": true,
    "completed": true,
    "effects": {
        "revealed": [
            {"playerId": "player_id2", "secretId": 123}
        ],
        "hidden": [
            {"playerId": "player_id2", "secretId": 456}
        ],
        "transferred": [
            {
                "fromPlayerId": "player_id2",
                "toPlayerId": "player_id1",
                "secretId": 789,
                "faceDown": true
            }
        ]
    },
    "nextAction": {
        "type": "selectOwnSecret",
        "allowedPlayers": ["player_id2"]
    }
}
```

**Permisos por tipo de paso**
- `selectPlayer/selectPlayerAndSecret`: solo el jugador que bajó el set
- `selectOwnSecret`: solo el jugador objetivo

**Validaciones**
- targetPlayerId debe estar en allowedPlayers
- Para revelar: secreto debe estar oculto en el set del objetivo
- Para Pyne: secreto debe estar revelado
- Concurrencia: validar que el estado no haya cambiado

**Errores por endpoint**
- 400 bad_request: targetPlayerId o secretId inválidos
- 403 forbidden: usuario no autorizado para el paso actual
- 404 not_found: actionId no existe o no pertenece al juego
- 409 conflict: el estado cambió y el paso ya no es válido
- 500 server_error: error inesperado

**Ejemplo curl**
```bash
curl -s -X POST "http://localhost:8000/api/game/42/detective-action" \
-H "Content-Type: application/json" \
-H "HTTP_USER_ID: 7" \
-d '{
    "actionId": "action_abc123",
    "targetPlayerId": "8",
    "secretId": 123
}' | jq .
```

### 4.11 POST /api/game/{room_id}/cards_off_the_table

**Descripción**: Fuerza a un jugador objetivo a descartar todas sus cartas "Not so fast..." (NSF). Esta acción no puede ser cancelada por NSF.

**Nota**: Para entender el flujo completo de acciones y su interacción con la tabla ActionsPerTurn, consultar [actions-turn-flow.md](actions-turn-flow.md)

**Path params**: 
- room_id: integer

**Body**
```json
{
    "targetPlayerId": "player_id"
}
```

**Comportamiento**
- Verifica si el jugador objetivo tiene cartas NSF en su mano (is_in = 'HAND')
- Descarta la carta de evento "Cards off the table" usada
- Mueve todas las cartas NSF del jugador objetivo al mazo de descarte
- Repone cartas del mazo:
  - Al jugador que usó la carta de evento (1 carta)
  - Al jugador objetivo (tantas cartas como NSF descartó)
- Actualiza las posiciones en las manos de ambos jugadores y el mazo de descarte
- Emite eventos WebSocket para notificar los cambios

**Responses**

**200 OK**
```json
{
    "success": true,
    "eventCardDiscarded": {
        "cardId": 25,
        "name": "Cards off the table",
        "type": "EVENT"
    },
    "discardedNSFCards": [
        {
            "cardId": 14,
            "previousPosition": 2,
            "name": "Not so fast",
            "type": "INSTANT"
        },
        {
            "cardId": 14,
            "previousPosition": 5,
            "name": "Not so fast",
            "type": "INSTANT"
        }
    ],
    "sourcePlayerHand": {
        "player_id": "source_id",
        "drawnCard": {
            "cardId": 30,
            "position": 3,
            "type": "DETECTIVE"
        }
    },
    "targetPlayerHand": {
        "player_id": "target_id",
        "discardedPositions": [2, 5],
        "drawnCards": [
            {
                "cardId": 31,
                "position": 2,
                "type": "EVENT"
            },
            {
                "cardId": 32,
                "position": 5,
                "type": "DETECTIVE"
            }
        ],
        "remainingCards": [
            {
                "cardId": 5,
                "position": 1,
                "type": "DETECTIVE"
            },
            {
                "cardId": 8,
                "position": 3,
                "type": "DETECTIVE"
            },
            {
                "cardId": 17,
                "position": 4,
                "type": "EVENT"
            },
            {
                "cardId": 21,
                "position": 6,
                "type": "EVENT"
            }
        ]
    },
    "discard": {
        "top": {"id": 14, "name": "Not so fast", "type": "INSTANT"},
        "count": 6
    },
    "deck": {
        "remaining": 33
    }
}
```

**Errores por endpoint**
- 400 bad_request: jugador objetivo inválido
- 403 forbidden: no es el turno del jugador
- 404 not_found: partida no encontrada
- 500 server_error: error inesperado

### 4.12 POST /api/game/{room_id}/event/another-victim

**Descripción**: Permite al jugador activo reclamar un set de detective existente de otro jugador.

**Nota**: Para entender el flujo completo de acciones y su interacción con la tabla ActionsPerTurn, consultar [actions-turn-flow.md](actions-turn-flow.md)

**Path params**: 
- room_id: integer

**Body**
```json
{
    "originalOwnerId": "player_id",
    "setPosition": 1
}
```

**Comportamiento**
- Valida que el set exista (cartas con is_in = 'DETECTIVE_SET' y position específica)
- Verifica que pertenezca al jugador original (player_id)
- Transfiere la propiedad al jugador activo actualizando player_id
- Mantiene el estado y position de las cartas
- Emite eventos WebSocket para notificar el cambio

**Responses**

**200 OK**
```json
{
    "success": true,
    "transferredSet": {
        "position": 1,
        "cards": [
            {
                "cardId": 5,
                "name": "Miss Marple",
                "type": "DETECTIVE"
            },
            {
                "cardId": 4,
                "name": "Harley Quin Wildcard",
                "type": "DETECTIVE"
            }
        ],
        "newOwnerId": "player_id",
        "originalOwnerId": "old_player_id"
    }
}
```

**Errores por endpoint**
- 400 bad_request: set inválido o no pertenece a otro jugador
- 403 forbidden: no es el turno del jugador
- 404 not_found: set no encontrado
- 500 server_error: error inesperado

### 4.13 POST /api/game/{room_id}/event/look-into-ashes

**Descripción**: Permite al jugador ver las 5 cartas superiores del mazo de descarte y tomar una.

**Nota**: Para entender el flujo completo de acciones y su interacción con la tabla ActionsPerTurn, consultar [actions-turn-flow.md](actions-turn-flow.md)

**Path params**: 
- room_id: integer

**Comportamiento en dos pasos**

**Paso 1 - Mostrar cartas disponibles**
La visualización de las cartas disponibles puede implementarse de dos maneras:

a) Mediante endpoint GET (implementación opcional):
GET /api/game/{room_id}/event/look-into-ashes/available

**Response 200**
```json
{
    "availableCards": [
        {"id": 14, "name": "Not so fast", "type": "INSTANT"},
        {"id": 5, "name": "Miss Marple", "type": "DETECTIVE"}, ...
    ]
}
```

b) A través del estado del juego (recomendado):
Las cartas disponibles del mazo de descarte se pueden obtener del estado actual de la partida, que se mantiene actualizado mediante eventos WebSocket. El cliente puede acceder a la información del mazo de descarte y sus cartas visibles directamente del estado del juego.

**Paso 2 - Seleccionar carta**
POST /api/game/{room_id}/event/look-into-ashes/select

**Path params**: 
- room_id: integer

**Headers**:
- HTTP_USER_ID: integer (ID del jugador que realiza la acción)

**Body**
```json
{
    "cardId": 14
}
```

**Response 200**
```json
{
    "success": true,
    "selectedCard": {
        "id": 14,
        "name": "Not so fast",
        "type": "INSTANT"
    },
    "hand": {
        "player_id": 7,
        "cards": [...]
    },
    "discard": {
        "top": {"id": 5, "name": "Miss Marple", "type": "DETECTIVE"},
        "count": 4
    }
}
```

**Errores por endpoint**
- 400 bad_request: carta seleccionada inválida
- 403 forbidden: no es el turno del jugador
- 404 not_found: carta no encontrada en el descarte
- 409 conflict: estado del juego cambió
- 500 server_error: error inesperado

### 4.14 POST /api/game/{room_id}/event/one-more

**Descripción**: Permite agregar un secreto revelado al set de secretos de cualquier jugador, ocultándolo.

**Nota**: Para entender el flujo completo de acciones y su interacción con la tabla ActionsPerTurn, consultar [actions-turn-flow.md](actions-turn-flow.md)

**Path params**: 
- room_id: integer

**Body**
```json
{
    "secretId": 123,
    "targetPlayerId": "player_id"
}
```

**Comportamiento**
- Valida que el secreto esté revelado
- Mueve el secreto al set del jugador objetivo
- Oculta el secreto (hidden = true)
- Emite eventos WebSocket para notificar cambios

**Responses**

**200 OK**
```json
{
    "success": true,
    "effect": {
        "secretId": 123,
        "originalOwnerId": "player_1",
        "newOwnerId": "player_2",
        "hidden": true
    }
}
```

**Errores por endpoint**
- 400 bad_request: secreto no está revelado o jugador inválido
- 403 forbidden: no es el turno del jugador
- 404 not_found: secreto no encontrado
- 500 server_error: error inesperado

### 4.15 POST /api/game/{room_id}/event/delay-murderer-escape

**Descripción**: Permite tomar hasta 5 cartas del tope del descarte y colocarlas en el mazo regular en orden especificado.

**Nota**: Para entender el flujo completo de acciones y su interacción con la tabla ActionsPerTurn, consultar [actions-turn-flow.md](actions-turn-flow.md)

**Path params**: 
- room_id: integer

**Paso 1 - Ver cartas disponibles**
La visualización de las cartas disponibles puede implementarse de dos maneras:

a) Mediante endpoint GET (implementación opcional):
GET /api/game/{room_id}/event/delay-murderer-escape/available

**Response 200**
```json
{
    "availableCards": [
        {
            "cardId": 14,
            "name": "Not so fast",
            "type": "INSTANT",
            "position": 1
        },
        {
            "cardId": 5,
            "name": "Miss Marple",
            "type": "DETECTIVE",
            "position": 2
        },
        {
            "cardId": 8,
            "name": "Parker Pyne",
            "type": "DETECTIVE",
            "position": 3
        }
    ],
    "count": 3
}
```

b) A través del estado del juego (recomendado):
Las cartas disponibles se pueden obtener del estado actual de la partida, que se mantiene actualizado mediante eventos WebSocket. El cliente puede acceder a la información del mazo de descarte y sus cartas visibles directamente del estado del juego.
```

**Paso 2 - Seleccionar cartas**
- POST /api/game/{room_id}/event/delay-murderer-escape

**Body**
```json
{
    "cardsToMove": 2
}
```

**Comportamiento**
- Verifica cantidad de cartas disponibles en el tope del descarte
- Mueve las cartas al mazo en el orden especificado
- Actualiza posiciones en ambos mazos
- Emite eventos WebSocket para notificar cambios

**Responses**

**200 OK**
```json
{
    "success": true,
    "movedCards": [
        {"id": 14, "position": 1},
        {"id": 5, "position": 2}
    ],
    "deck": {
        "remaining": 7
    },
    "discard": {
        "top": {"id": 8, "name": "Parker Pyne", "type": "DETECTIVE"},
        "count": 1
    }
}
```

**Errores por endpoint**
- 400 bad_request: selección de cartas inválida
- 403 forbidden: no es el turno del jugador
- 409 conflict: estado del juego cambió
- 500 server_error: error inesperado

### 4.16 POST /api/game/{room_id}/early_train_to_paddington

**Descripción**: Toma 6 cartas del tope del mazo regular y las coloca boca arriba en el descarte. La carta evento se elimina del juego.

**Path params**: 
- room_id: integer

**Comportamiento**
- Valida que la carta esté en la mano del jugador
- Mueve 6 cartas del mazo al descarte (o todas si hay menos)
- Elimina la carta Early Train del juego
- Reordena posiciones en ambos mazos
- Emite eventos WebSocket para notificar cambios

**Responses**

**200 OK**
```json
{
    "success": true,
    "movedToDeck": [
        {"id": 14, "name": "Not so fast", "type": "INSTANT"},
        {"id": 5, "name": "Miss Marple", "type": "DETECTIVE"}
    ],
    "deck": {
        "remaining": 30
    },
    "discard": {
        "top": {"id": 5, "name": "Miss Marple", "type": "DETECTIVE"},
        "count": 8
    }
}
```

**Errores por endpoint**
- 403 forbidden: no es el turno del jugador
- 404 not_found: carta no está en la mano del jugador
- 409 conflict: estado del juego cambió
- 500 server_error: error inesperado

### 4.17 DELETE /api/game_join/{room_id}/leave

**Descripción**: Endpoint para que el host cancele una partida NO iniciada (desvinculando a todos los jugadores de la sala) o para que un jugador no-host abandone la partida. El comportamiento depende de si quien invoca es el host o no.

**Ruta**: DELETE /api/game_join/{room_id}/leave

**Headers**:
- HTTP_USER_ID: integer (ID del jugador que realiza la solicitud)

**Path params**:
- room_id: integer

**Comportamiento / Flujo**
- Validar que `room_id` existe y que `Room.status == "WAITING"`.
- Identificar al jugador mediante `HTTP_USER_ID` y verificar que `Player.id_room == room_id`.
- Si el jugador es el host (`Player.is_host == true`):
    - Actualizar todos los jugadores de la sala: `UPDATE Player SET id_room = NULL WHERE id_room = room_id`.
    - Eliminar la sala: `DELETE FROM Room WHERE id = room_id`.
    - Emitir evento WS `game_cancelled` al room `game_{room_id}` con payload `{ "room_id": number, "timestamp": "ISO-8601" }`.
- Si el jugador NO es el host:
    - Actualizar solo al jugador solicitante: `UPDATE Player SET id_room = NULL WHERE id = player_id`.
    - Emitir evento WS `player_left` al room `game_{room_id}` con payload `{ "player_id": number, "players_count": number, "timestamp": "ISO-8601" }`.

**Validaciones / Errores**
- 404 not_found: `room_id` no existe
- 403 forbidden: el jugador no pertenece a esta sala (`Player.id_room != room_id`)
- 409 conflict: `room.status != "WAITING"` (la partida ya inició o terminó)
- 500 server_error: error inesperado

**Responses**

**200 OK**
```json
{
    "success": true
}
```

**Ejemplos**

Host cancela la sala (curl):
```bash
curl -s -X DELETE "http://localhost:8000/api/game_join/42/leave" \
    -H "Content-Type: application/json" \
    -H "HTTP_USER_ID: 7" | jq .
```

Jugador no-host abandona la sala (curl):
```bash
curl -s -X DELETE "http://localhost:8000/api/game_join/42/leave" \
    -H "Content-Type: application/json" \
    -H "HTTP_USER_ID: 9" | jq .
```

### 4.18 Not So Fast

**4.18.a POST /api/game/{room_id}/start-action**
- **Descripción**: Iniciar una acción que puede ser contrarrestada con Not So Fast.
- **Path params**: `room_id` (integer)
- **Body**: `{ "playerId": integer, "cardIds": [integer], "additionalData": object }`
- **Responses**:
  - `200 OK`: Acción iniciada con información de cancelabilidad y tiempo restante.
  - `404 Not Found`: Sala no encontrada.
  - `403 Forbidden`: No es el turno del jugador.

**4.18.b POST /api/game/{room_id}/instant/not-so-fast**
- **Descripción**: Jugar una carta Not So Fast para cancelar una acción.
- **Path params**: `room_id` (integer)
- **Body**: `{ "actionId": integer, "playerId": integer, "cardId": integer }`
- **Responses**:
  - `200 OK`: Carta Not So Fast jugada exitosamente.
  - `404 Not Found`: Acción o carta no encontrada.
  - `400 Bad Request`: Carta no está en la mano del jugador.

**4.18.c POST /api/game/{room_id}/instant/not-so-fast/cancel**
- **Descripción**: Ejecutar una acción que fue cancelada por Not So Fast.
- **Path params**: `room_id` (integer)
- **Body**: `{ "actionId": integer, "playerId": integer, "cardIds": [integer], "additionalData": object }`
- **Responses**:
  - `200 OK`: Acción cancelada ejecutada exitosamente.
  - `404 Not Found`: Acción no encontrada.
  - `403 Forbidden`: No autorizado para ejecutar la acción.

### 4.19 Take Deck

**4.19 POST /game/{room_id}/take-deck**
- **Descripción**: Robar cartas del mazo regular.
- **Path params**: `room_id` (integer)
- **Body**: `{ "cantidad": integer }`
- **Responses**:
  - `200 OK`: Cartas robadas exitosamente.
  - `404 Not Found`: Sala o partida no encontrada.
  - `403 Forbidden`: No es el turno del jugador.
  - `400 Bad Request`: Mazo vacío.

### 4.20 Add to Set

**4.20 POST /api/game/{room_id}/add-to-set**
- **Descripción**: Agregar un detective a un set existente.
- **Path params**: `room_id` (integer)
- **Body**: `{ "owner": integer, "setType": string, "cardId": integer }`
- **Responses**:
  - `200 OK`: Acción registrada y notificaciones enviadas.
  - `404 Not Found`: Sala no encontrada.
  - `409 Conflict`: La partida no ha comenzado.

### 4.21 Dead Card Folly

**4.21.a POST /api/game/{room_id}/event/dead-card-folly/play**
- **Descripción**: Jugar la carta "Dead Card Folly" y elegir dirección de intercambio.
- **Path params**: `room_id` (integer)
- **Body**: `{ "player_id": integer, "card_id": integer, "direction": string }`
- **Responses**:
  - `200 OK`: Acción registrada y notificaciones enviadas.
  - `404 Not Found`: Sala, partida o carta no encontrada.
  - `403 Forbidden`: No es el turno del jugador.

**4.21.b POST /api/game/{room_id}/event/dead-card-folly/select-card**
- **Descripción**: Seleccionar una carta para el intercambio.
- **Path params**: `room_id` (integer)
- **Body**: `{ "action_id": integer, "card_id": integer, "player_id": integer }`
- **Responses**:
  - `200 OK`: Carta seleccionada exitosamente.
  - `404 Not Found`: Acción o carta no encontrada.
  - `400 Bad Request`: Acción no está pendiente o carta no está en la mano.

### 4.22 Delay the Murderer's Escape

**4.22 POST /api/game/{room_id}/event/delay-murderer-escape**
- **Descripción**: Jugar la carta "Delay the Murderer's Escape" para mover cartas del descarte al mazo.
- **Path params**: `room_id` (integer)
- **Body**: `{ "card_id": integer, "cardsToMove": integer }`
- **Responses**:
  - `200 OK`: Cartas movidas exitosamente.
  - `404 Not Found`: Sala, partida o carta no encontrada.
  - `403 Forbidden`: No es el turno del jugador.



## 5. Eventos WebSocket

Esta sección define el contrato de eventos de WebSocket para el juego. El backend publica eventos al room de cada partida. El cliente escucha y actualiza la UI y el estado global.

### Canal y sesión
- **Canal por partida**: room "game_{room_id}"
- **Handshake**: header HTTP_USER_ID para identificar al usuario
- **Sesión**: cada conexión se asocia a un user_id; el servidor gestiona entrada y salida de rooms

### Nombres de eventos y payloads

**connected**
- Emisor: servidor a cliente recién conectado
- Payload: `{ "message": "Conectado existosamente", "user_id": number, "room_id": number, "sid": string }`

**disconnected**
- Emisor: servidor a cliente recien conectado
- Payload: `{ "message": "Conectado existosamente", "user_id": number, "room_id": number, "sid": string }`

**player_connected**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "user_id": number, "room_id": number, "timestamp": "ISO-8601" }`

**player_disconnected**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "user_id": number, "room_id": number, "timestamp": "ISO-8601" }`

**error**
- Emisor: servidor a cliente
- Payload: `{ "message": string }`

**game_state_public**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "game_state_public", "room_id": number, "game_id": number, "status": string, "turno_actual": number, "jugadores": array, "mazos": object, "sets": array, "secretsFromAllPlayers": array, "timestamp": "ISO-8601" }`

**game_state_private**
- Emisor: servidor a cliente específico
- Payload: `{ "type": "game_state_private", "user_id": number, "mano": array, "secretos": array, "timestamp": "ISO-8601" }`

**game_ended**
- Emisor: servidor a cliente específico
- Payload: `{ "type": "game_ended", "user_id": number, "ganaste": boolean, "winners": array, "reason": string, "timestamp": "ISO-8601" }`

**detective_action_started**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "detective_action_started", "player_id": number, "set_type": string, "message": string, "timestamp": "ISO-8601" }`

**detective_target_selected**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "detective_target_selected", "player_id": number, "target_player_id": number, "set_type": string, "message": string, "timestamp": "ISO-8601" }`

**detective_action_request**
- Emisor: servidor al cliente objetivo
- Payload: `{ "type": "detective_action_request", "action_id": string, "requester_id": number, "set_type": string, "target_player_id": number, "message": string, "timestamp": "ISO-8601" }`

**detective_action_complete**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "detective_action_complete", "action_type": string, "player_id": number, "target_player_id": number, "secret_id": number, "action": string, "wildcard_used": boolean, "secret_data": object, "message": string, "timestamp": "ISO-8601" }`

**game_cancelled**
- Emisor: servidor a todos en game_{room_id}
- Uso: notificar que la sala fue cancelada por el host antes de iniciar la partida
- Payload: `{ "type": "game_cancelled", "room_id": number, "timestamp": "ISO-8601" }`

**player_left**
- Emisor: servidor a todos en game_{room_id}
- Uso: notificar que un jugador abandonó la sala en estado WAITING
- Payload: `{ "type": "player_left", "player_id": number, "players_count": number, "players": array, "timestamp": "ISO-8601" }`

**event_action_started**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "event_action_started", "player_id": number, "event_type": string, "card_name": string, "step": string, "message": string, "timestamp": "ISO-8601" }`

**event_step_update**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "event_step_update", "player_id": number, "event_type": string, "step": string, "message": string, "data": object, "timestamp": "ISO-8601" }`

**event_action_complete**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "event_action_complete", "player_id": number, "event_type": string, "timestamp": "ISO-8601" }`

**dead_card_folly_select_card**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "dead_card_folly_select_card", "action_id": number, "direction": string, "player_id": number, "player_name": string, "message": string, "timestamp": "ISO-8601" }`

**dead_card_folly_complete**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "dead_card_folly_complete", "action_id": number, "direction": string, "players_count": number, "message": string, "timestamp": "ISO-8601" }`

**player_must_draw**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "player_must_draw", "player_id": number, "cards_to_draw": number, "message": string, "timestamp": "ISO-8601" }`

**card_drawn_simple**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "card_drawn_simple", "player_id": number, "drawn_from": string, "cards_remaining": number, "message": string, "timestamp": "ISO-8601" }`

**turn_finished**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "turn_finished", "player_id": number, "message": string, "timestamp": "ISO-8601" }`

**social_disgrace_update**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "social_disgrace_update", "game_id": number, "players_in_disgrace": array, "message": string, "change": object, "timestamp": "ISO-8601" }`

**valid_action**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "valid_action", "action_id": number, "player_id": number, "action_type": string, "action_name": string, "cancellable": boolean, "timestamp": "ISO-8601" }`

**nsf_counter_start**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "nsf_counter_start", "action_id": number, "nsf_action_id": number, "player_id": number, "action_type": string, "action_name": string, "time_remaining": number, "timestamp": "ISO-8601" }`

**nsf_counter_tick**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "nsf_counter_tick", "action_id": number, "remaining_time": number, "elapsed_time": number, "timestamp": "ISO-8601" }`

**nsf_played**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "nsf_played", "action_id": number, "nsf_action_id": number, "player_id": number, "card_id": number, "player_name": string, "message": string, "timestamp": "ISO-8601" }`

**nsf_counter_complete**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "nsf_counter_complete", "action_id": number, "final_result": string, "message": string, "timestamp": "ISO-8601" }`

**cancelled_action_executed**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "type": "cancelled_action_executed", "action_id": number, "player_id": number, "message": string, "timestamp": "ISO-8601" }`

### Secuencia típica por endpoints

**POST /game/{room_id}/join**
- Emitir: 

**POST /game/{room_id}/start**
- Emitir: game_started, hand_updated (por jugador), secrets_updated (por jugador), deck_updated, discard_updated

**POST /game/{room_id}/discard**
- Emitir al solicitante: action_result con ActionResult + hand
- Emitir a todos: deck_updated, discard_updated, turn_updated

**POST /game/{room_id}/skip**
- Emitir al solicitante: action_result con 1 discarded + 1 drawn + hand
- Emitir a todos: deck_updated, discard_updated, turn_updated

**POST /api/game/{room_id}/play-detective-set** (Poirot/Marple/Parker Pyne)
- Emitir al solicitante: action_result con el set creado
- Emitir a todos: detective_set_created con set público
- En caso de cancelación, no hay eventos a emitir

**POST /api/game/{room_id}/detective-action** (Selección de jugador/secreto)
- Emitir al solicitante: action_result con selección realizada
- Emitir a todos: secret_revealed o secret_transferred según corresponda
- En caso de cancelación, no hay eventos a emitir

**POST /api/game/{room_id}/event/cards-off-table**
- Emitir al objetivo: hand_updated con nueva mano
- Emitir a todos: discard_updated con nuevas cartas NSF
- En caso de cancelación, no hay eventos a emitir

**POST /api/game/{room_id}/event/another-victim**
- Emitir al solicitante: action_result con set transferido
- Emitir a todos: detective_set_transferred
- En caso de cancelación, no hay eventos a emitir

**GET /api/game/{room_id}/event/look-into-ashes/available**
- Sin eventos WebSocket

**POST /api/game/{room_id}/event/look-into-ashes/select**
- Emitir al solicitante: hand_updated con nueva carta
- Emitir a todos: discard_updated
- En caso de cancelación, no hay eventos a emitir

**POST /api/game/{room_id}/event/and-then-one-more**
- Emitir al objetivo: secrets_updated con nuevo secreto
- Emitir a todos: secret_transferred
- En caso de cancelación, no hay eventos a emitir

**GET /api/game/{room_id}/event/delay-murderer-escape/available**
- Sin eventos WebSocket

**POST /api/game/{room_id}/event/delay-murderer-escape**
- Emitir a todos: deck_updated, discard_updated
- En caso de cancelación, no hay eventos a emitir

**POST /api/game/{room_id}/event/early-train**
- Emitir a todos: deck_updated, discard_updated
- Emitir al solicitante: hand_updated (sin la carta Early Train)

**Fin de partida**
- Emitir: game_finished, y opcionalmente game_state final


## 6. Estructura de Carpetas

La estructura del proyecto sigue una organización modular para facilitar el mantenimiento y la escalabilidad:

```
project-backend/
├── app/                          # Aplicación principal
│   ├── main.py                   # Punto de entrada de la aplicación FastAPI
│   ├── config.py                 # Configuración general
│   ├── db/                       # Capa de acceso a datos
│   │   ├── crud.py              # Operaciones CRUD básicas
│   │   ├── database.py          # Configuración de SQLAlchemy y base de datos
│   │   ├── events.py            # Lógica específica de listeners de base de datos
│   │   └── models.py            # Modelos SQLAlchemy (tablas)
│   ├── routes/                   # Endpoints REST de la API
│   │   ├── add_to_set.py        # Agregar carta a set de detective
│   │   ├── another_victim.py    # Carta evento "Another Victim"
│   │   ├── cards_off_the_table.py # Carta evento "Cards Off the Table"
│   │   ├── dead_card_folly.py   # Carta evento "Dead Card Folly"
│   │   ├── delay.py             # Carta evento "Delay the Murderer's Escape"
│   │   ├── detective_action.py  # Acciones de sets de detective
│   │   ├── discard.py           # Descartar cartas
│   │   ├── draft.py             # Mazo de draft
│   │   ├── early_train_to_paddington.py # Carta evento "Early Train to Paddington"
│   │   ├── finish_turn.py       # Finalizar turno
│   │   ├── game.py              # Operaciones básicas de partida
│   │   ├── get_list.py          # Listado de partidas disponibles
│   │   ├── join.py              # Unirse a partida
│   │   ├── leave_game.py        # Abandono de partida
│   │   ├── look_ashes.py        # Carta evento "Look Into Ashes"
│   │   ├── not_so_fast.py       # Carta instantánea "Not So Fast"
│   │   ├── one_more.py          # Carta evento "And Then There Was One More"
│   │   └── play_detective_set.py # Bajar sets de detective
│   ├── schemas/                  # Esquemas Pydantic para validación
│   │   ├── dead_card_folly_schema.py # Esquemas para Dead Card Folly
│   │   ├── delay_schema.py      # Esquemas para Delay the Murderer's Escape
│   │   ├── detective_action_schema.py # Esquemas para acciones de detective
│   │   ├── detective_set_schema.py # Esquemas para sets de detective
│   │   ├── discard_schema.py    # Esquemas para descarte
│   │   ├── draft.py             # Esquemas para mazo de draft
│   │   ├── game.py              # Esquemas básicos de partida
│   │   ├── game_status_schema.py # Esquemas para estado de juego
│   │   ├── __init__.py          # Inicialización del módulo schemas
│   │   ├── leave_game.py        # Esquemas para abandono de partida
│   │   ├── look_ashes_schema.py # Esquemas para Look Into Ashes
│   │   ├── not_so_fast_schema.py # Esquemas para Not So Fast
│   │   ├── one_more_schema.py   # Esquemas para And Then There Was One More
│   │   └── player.py            # Esquemas de jugador
│   ├── services/                 # Lógica de negocio
│   │   ├── counter_timeout_handler.py # Manejo de timeouts y contadores
│   │   ├── dead_card_folly_service.py # Lógica de Dead Card Folly
│   │   ├── detective_action_service.py # Lógica de acciones de detective
│   │   ├── detective_set_service.py # Lógica de sets de detective
│   │   ├── discard.py           # Lógica de descarte
│   │   ├── draft_service.py     # Lógica del mazo de draft
│   │   ├── early_train_discard.py # Lógica de Early Train to Paddington
│   │   ├── game_service.py      # Lógica principal del juego
│   │   ├── game_status_service.py # Estado y validaciones de partida
│   │   ├── leave_game_service.py # Lógica de abandono de partida
│   │   ├── not_so_fast_service.py # Lógica de Not So Fast
│   │   ├── social_disgrace_service.py # Lógica de desgracia social
│   │   ├── take_deck.py         # Lógica para robar cartas del mazo
│   │   └── timer_manager.py     # Gestión de timers del juego
│   ├── sockets/                  # Gestión de WebSocket
│   │   ├── socket_events.py     # Definición de eventos WebSocket
│   │   ├── socket_manager.py    # Gestor de conexiones WebSocket
│   │   └── socket_service.py    # Lógica de notificaciones por WebSocket
│   └── tests/                    # Tests unitarios e integración con pytest
├── actions-turn-flow.md          # Documentación del flujo de acciones por turno
├── create_db.py                  # Script para creación de base de datos
├── documentacion-API.md          # Esta documentación de la API
├── README.md                     # Documentación general del proyecto
└── requirements.txt              # Dependencias del proyecto Python

```

### Notas sobre la estructura:

- **app/**: Contiene toda la aplicación FastAPI con separación clara de responsabilidades
- **routes/**: Cada archivo maneja endpoints específicos organizados por funcionalidad de carta o acción
- **schemas/**: Esquemas Pydantic para validación de requests/responses, organizados por funcionalidad
- **services/**: Lógica de negocio separada de la presentación (routes) y persistencia (db)
- **sockets/**: Manejo completo de WebSocket para notificaciones en tiempo real
- **tests/**: Tests unitarios e integración con cobertura completa
- **Archivos raíz**: Documentación, configuración y scripts de utilidad del proyecto

## 7. Changelog

- **2025-09-22**: Documentación Inicial de la API, basada en los tickets generados.
- **2025-10-9**: Actualización de la documentación acorde a las nuevas implementaciones del Sprint 2. 
- **2025-10-18**: Se agregó el endpoint DELETE `/api/game_join/{room_id}/leave` (host cancela / jugador abandona) y la documentación de los eventos WebSocket `game_cancelled` y `player_left`.
- **2025-11-10**: Actualización de la estructura de carpetas del proyecto reflejando la organización actual. Actualización de esquemas de base de datos (sección 3.2) con nuevos modelos como SocialDisgracePlayer. Adición de endpoints faltantes (4.18-4.25) incluyendo Not So Fast, One More, take deck, y cartas de eventos. Actualización integral de eventos WebSocket (sección 5) con payloads completos según implementación actual en socket_service.py.

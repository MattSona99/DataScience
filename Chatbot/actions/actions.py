from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.forms import FormValidationAction
from typing import Any, Text, Dict, List, Optional
import re
import difflib
import pandas as pd

# Carico il dataset una volta sola all'avvio dell'action server
df_games = pd.DataFrame()
try:
    df_games = pd.read_csv("./dataset/vintage_games_clean.csv")
    print("Loaded games dataset with columns:", df_games.columns.tolist())
except FileNotFoundError:
    print("vintage_games_clean.csv file not found. Check the path!")
    pass

SLOT_TO_COLUMN = {
    "console":      "Console",
    "genre":        "Genre",
    "publisher":    "Publisher",
    # se vuoi, puoi aggiungere anche altri
}

SKIP_VALUE = "SKIP"

def _build_value_map(column_name: str) -> Dict[str, str]:
    """Crea una mappa lowercase -> valore originale per una colonna del dataset."""
    if df_games.empty or column_name not in df_games.columns:
        return {}
    uniques = (
        df_games[column_name]
        .dropna()
        .astype(str)
        .unique()
    )
    return {u.lower(): u for u in uniques}

VALUE_MAPS: Dict[str, Dict[str, str]] = {
    slot: _build_value_map(col)
    for slot, col in SLOT_TO_COLUMN.items()
}

def _closest_dataset_value(slot_name: str, user_value: str) -> Optional[str]:
    """
    Ritorna il valore del dataset più simile a quello inserito dall'utente
    (o None se non trova niente di sufficientemente simile).
    """
    value_map = VALUE_MAPS.get(slot_name, {})
    if not value_map:
        return None

    user_norm = user_value.strip().lower()
    keys = list(value_map.keys())
    matches = difflib.get_close_matches(user_norm, keys, n=1, cutoff=0.6)
    if not matches:
        return None

    best_key = matches[0]
    return value_map[best_key]  # valore originale con maiuscole ecc.

def _extract_first_number(text: str) -> Optional[float]:
    """
    Estrae il primo numero (intero o decimale) dal testo.
    Esempi:
        "my budget is 25" -> 25.0
        "around 10.5 is fine" -> 10.5
    """
    if not text:
        return None
    match = re.search(r"\d+(\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None

class ValidateGamePreferencesForm(FormValidationAction):

    def name(self) -> Text:
        return "validate_game_preferences_form"

    # ---------- VALIDAZIONE NUMERICA GENERICA ----------

    def _validate_positive_number(
        self,
        slot_name: str,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        invalid_utter: Text,
    ) -> Dict[Text, Any]:
        """
        1. Se lo slot ha già un valore numerico valido -> lo usa.
        2. Se lo slot è None o non numerico -> prova a estrarre un numero dal testo utente.
        3. Se non trova niente -> manda messaggio di errore e svuota lo slot.
        4. Se il numero è negativo -> errore e slot None.
        """
        print(f"[DEBUG] validating {slot_name}, slot_value={slot_value}, text='{tracker.latest_message.get('text','')}'")
        value: Optional[float] = None
        text = tracker.latest_message.get("text", "").strip().lower()
        
        pattern = r"\b(skip|no|nope|nah)\b"
        # Caso 1: lo slot arriva già con qualcosa (es. entity "25")
        if slot_value is not None:
            try:
                value = float(slot_value)
            except (TypeError, ValueError):
                value = None

        # Caso 2: provo a estrarlo dal testo dell'ultima user message
        if value is None:
            # special case "no limit" per used_price
            if slot_name == "used_price" and "no limit" in text:
                return {"used_price": 1000}

            value = _extract_first_number(text)
            
        # Caso 3: check per skip
        if re.search(pattern, text):
            dispatcher.utter_message(
                text=f"Ok, I will not use the filter '{slot_name}'."
            )
            return {slot_name: SKIP_VALUE}

        if value is None:
            dispatcher.utter_message(response=invalid_utter)
            return {slot_name: None}

        if value < 0:
            dispatcher.utter_message(text="Please provide a non-negative number.")
            return {slot_name: None}

        # vincoli specifici:
        # release_year: 2004–2010
        if slot_name == "release_year":
            year = int(value)
            if year < 2004 or year > 2010:
                dispatcher.utter_message(response=invalid_utter)
                return {"release_year": None}
            return {"release_year": year}

        # review_score in 0–100
        if slot_name == "review_score":
            score = float(value)
            if score < 0 or score > 100:
                dispatcher.utter_message(response=invalid_utter)
                return {"review_score": None}
            return {"review_score": score}

        # max_player intero >=1
        if slot_name == "max_player":
            players = int(value)
            if players <= 0 or players > 8:
                dispatcher.utter_message(response=invalid_utter)
                return {"max_player": None}
            return {"max_player": players}

        # used_price: solo non negativo
        if slot_name == "used_price":
            return {"used_price": float(value)}

        # fallback generico
        return {slot_name: value}

    # ---- metodi validate_ per i numerici ----

    def validate_release_year(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        print("[DEBUG] validate_release_year called")
        print("  slot_value:", slot_value)
        print("  latest text:", tracker.latest_message.get("text", ""))
        return self._validate_positive_number(
            "release_year", slot_value, dispatcher, tracker, "utter_release_year_invalid"
        )

    def validate_used_price(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        print("[DEBUG] validate_used_price called")
        print("  slot_value:", slot_value)
        print("  latest text:", tracker.latest_message.get("text", ""))
        return self._validate_positive_number(
            "used_price", slot_value, dispatcher, tracker, "utter_used_price_invalid"
        )

    def validate_review_score(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        print("[DEBUG] validate_review_score called")
        print("  slot_value:", slot_value)
        print("  latest text:", tracker.latest_message.get("text", ""))
        return self._validate_positive_number(
            "review_score", slot_value, dispatcher, tracker, "utter_review_score_invalid"
        )

    def validate_max_player(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        print("[DEBUG] validate_max_player called")
        print("  slot_value:", slot_value)
        print("  latest text:", tracker.latest_message.get("text", ""))
        return self._validate_positive_number(
            "max_player", slot_value, dispatcher, tracker, "utter_max_player_invalid"
        )

    # ---------- VALIDAZIONE TESTUALE + FUZZY MATCH ----------

    def _validate_categorical_from_dataset(
        self,
        slot_name: str,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        invalid_utter: Text,
    ) -> Dict[Text, Any]:
        print(f"[DEBUG] validating {slot_name}, slot_value={slot_value}")
        text = tracker.latest_message.get("text", "").strip().lower()
        
        pattern = r"\b(skip|no|nope|nah)\b"
        
        if not slot_value:
            dispatcher.utter_message(response=invalid_utter)
            return {slot_name: None}
        
        if re.search(pattern, text):
            dispatcher.utter_message(
                text=f"Ok, I will not use the filter '{slot_name}'."
            )
            return {slot_name: SKIP_VALUE}

        user_value = str(slot_value).strip()
        suggestion = _closest_dataset_value(slot_name, user_value)

        if suggestion is None:
            dispatcher.utter_message(response=invalid_utter)
            return {slot_name: None}

        # se è diverso da quello scritto dall'utente, glielo dico
        if suggestion.lower() != user_value.lower():
            dispatcher.utter_message(
                text=f"I'll use '{suggestion}' for the {slot_name}, based on the closest match in the database."
            )

        return {slot_name: suggestion}

    def validate_console(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return self._validate_categorical_from_dataset(
            "console", slot_value, dispatcher, tracker, "utter_console_invalid"
        )

    def validate_genre(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return self._validate_categorical_from_dataset(
            "genre", slot_value, dispatcher, tracker, "utter_genre_invalid"
        )

    def validate_publisher(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return self._validate_categorical_from_dataset(
            "publisher", slot_value, dispatcher, tracker, "utter_publisher_invalid"
        )

    # ---------- ONLINE / MULTIPLATFORM (normalizzazione) ----------

    def validate_online(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        text = tracker.latest_message.get("text", "").strip().lower()
        
        pattern_skip = r"\b(skip)\b"
        
        pattern_online = r"\b(online|yes|on|of course)\b"
        pattern_offline = r"\b(offline|no|nope|nah)\b"
        
        
        if re.search(pattern_skip, text):
            dispatcher.utter_message(
                text=f"Ok, I will not use the filter 'online'."
            )
            return {"online": SKIP_VALUE}
        
        if re.search(pattern_offline, text):
            return {"online": "offline"}
        
        if re.search(pattern_online, text):
            return {"online": "online"}
        
        # se proprio non si capisce
        dispatcher.utter_message(response="utter_online_invalid")
        return {"online": None}

    def validate_multiplatform(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        text = tracker.latest_message.get("text", "").strip().lower()
        
        pattern_skip = r"\b(skip)\b"
        
        pattern_exclusive = r"\b(exclusive|single|only on)\b"
        pattern_multiplatform = r"\b(multi|multiplatform|available on multiple|also on)\b"
        
        if re.search(pattern_skip, text):
            dispatcher.utter_message(
                text=f"Ok, I will not use the filter 'multiplatform'."
            )
            return {"multiplatform": SKIP_VALUE}
        
        if re.search(pattern_exclusive, text):
            return {"multiplatform": "exclusive"}
        
        if re.search(pattern_multiplatform, text):
            return {"multiplatform": "multiplatform"}
        
        dispatcher.utter_message(response="utter_multiplatform_invalid")
        return {"multiplatform": None}


# ---------- SEARCH GAME ----------

class ActionSearchGame(Action):

    def name(self) -> Text:
        return "action_search_game"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        if df_games.empty:
            dispatcher.utter_message(text="Sorry, the game database is not available.")
            return []

        # Estraggo gli slot
        console = tracker.get_slot("console")
        genre = tracker.get_slot("genre")
        used_price = tracker.get_slot("used_price")
        release_year = tracker.get_slot("release_year")
        review_score = tracker.get_slot("review_score")
        max_player = tracker.get_slot("max_player")
        online = tracker.get_slot("online")
        multiplatform = tracker.get_slot("multiplatform")
        publisher = tracker.get_slot("publisher")

        print("[action_search_game] Slots:")
        print("  console:", console)
        print("  genre:", genre)
        print("  used_price:", used_price)
        print("  release_year:", release_year)
        print("  review_score:", review_score)
        print("  max_player:", max_player)
        print("  online:", online)
        print("  multiplatform:", multiplatform)
        print("  publisher:", publisher)

        df = df_games.copy()


        # Console
        if console not in (None, SKIP_VALUE):
            df = df[
                df["Console"]
                .astype(str)
                .str.lower()
                .str.contains(str(console).lower(), na=False)
            ]

        # Genere principale 
        if genre not in (None, SKIP_VALUE):
            df = df[
                df["Genre"]
                .astype(str)
                .str.lower()
                .str.contains(str(genre).lower(), na=False)
            ]

        # Prezzo usato 
        if used_price not in (None, SKIP_VALUE):
            try:
                max_price = float(used_price)
                df = df[df["Usedprice"] <= max_price]
            except (ValueError, TypeError):
                # Se non si riesce a convertire, ignora il filtro
                pass

        # Anno di uscita
        if release_year not in (None, SKIP_VALUE):
            try:
                year = int(release_year)
                df = df[df["YearReleased"] == year]
            except (ValueError, TypeError):
                pass

        # Review score minimo
        if review_score not in (None, SKIP_VALUE):
            try:
                min_score = float(review_score)
                df = df[df["Review Score"] >= min_score]
            except (ValueError, TypeError):
                pass

        # Numero massimo giocatori
        if max_player not in (None, SKIP_VALUE):
            try:
                max_p = int(max_player)
                df = df[df["MaxPlayers"] <= max_p]
            except (ValueError, TypeError):
                pass

        # Online (colonna 'Online' 0/1)
        if online not in (None, SKIP_VALUE):
            v = str(online).strip().lower()
            if v in {"true", "online"}:
                df = df[df["Online"] == 1]
            elif v in {"false", "offline"}:
                df = df[df["Online"] == 0]

        # Multiplatform 
        if multiplatform not in (None, SKIP_VALUE):
            v = str(multiplatform).strip().lower()
            if v in {"multiplatform"}:
                df = df[df["Multiplatform"] == 1]
            elif v in {"exclusive"}:
                df = df[df["Multiplatform"] == 0]
                
        # Publisher
        if publisher not in (None, SKIP_VALUE):
            df = df[
                df["Publisher"]
                .astype(str)
                .str.lower()
                .str.contains(str(publisher).lower(), na=False)
            ]

        # Costruisco la risposta
        shown_result: List[Text] = []

        if df.empty:
            dispatcher.utter_message(text="Sorry, I couldn't find any game with these filters.")
        else:
            # uso le colonne reali: 'Title', 'Console', 'Genre', 'Usedprice', 'YearReleased'
            cols = ["Title", "Console", "Genre", "Usedprice", "YearReleased"]
            missing = [c for c in cols if c not in df.columns]
            if missing:
                dispatcher.utter_message(
                    text=f"Internal error: expected columns {missing} not found in dataset."
                )
                return []

            recommended_games = df[cols].head(10)

            message_lines = ["Here are some game recommendations for you:"]
            for _, row in recommended_games.iterrows():
                title = row["Title"]
                cons = row["Console"]
                gen = row["Genre"]
                price = row["Usedprice"]
                year = int(row["YearReleased"]) if not pd.isna(row["YearReleased"]) else "N/A"

                message_lines.append(
                    f"------------------------------ \n \
                    Title: {title} \n \
                    Console: {cons} \n \
                    Genre: {gen} \n \
                    UsedPrice: {price} \n \
                    YearReleased: {year} \n \
                    ------------------------------ "
                )
                shown_result.append(title)

            dispatcher.utter_message(text="\n".join(message_lines))

        return [SlotSet("last_result", shown_result)]

class ActionResetGamePreferences(Action):

    def name(self) -> Text:
        return "action_reset_game_preferences"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        slots_to_reset = [
            "console",
            "genre",
            "used_price",
            "release_year",
            "review_score",
            "max_player",
            "online",
            "multiplatform",
            "publisher",
            "last_result",
        ]

        for slot in slots_to_reset:
            dispatcher.utter_message(text=f"Resetting slot '{slot}'.")

        return [SlotSet(slot, None) for slot in slots_to_reset]
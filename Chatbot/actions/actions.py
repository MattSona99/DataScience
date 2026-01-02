from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction
from rasa_sdk.forms import FormValidationAction
import math
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
    "subgenre":     "SubGenres",
    # se vuoi, puoi aggiungere anche altri
}

# Mappa: Parola chiave (o leggibile) -> Nome reale dello Slot
# Aggiungiamo varianti "umane" per aiutare il matching (es. 'budget' -> 'used_price')
slot_keywords = {
    "console": "console",
        "device": "console",
        "genre": "genre",
        "type": "genre",
        "release year": "release_year",
        "year": "release_year",
        "date": "release_year",
        "used price": "used_price",
        "price": "used_price",
        "budget": "used_price",
        "cost": "used_price",
        "review score": "review_score",
        "score": "review_score",
        "max player": "max_player",
        "players": "max_player",
        "online": "online",
        "internet": "online",
        "offline": "online",
        "on": "online",
        "off": "online",
        "multiplatform": "multiplatform",
        "exclusive": "multiplatform",
        "multi": "multiplatform",
        "single": "multiplatform",
        "publisher": "publisher",
        "developer": "publisher",
        "company": "publisher",
        "creators": "publisher",
        "maker": "publisher",
        "age rating": "age_rating",
        "rating": "age_rating",
        "age": "age_rating",
        "age limit": "age_rating",
        "limit": "age_rating",
    }

SKIP_VALUE = "SKIP"

def _build_value_map(column_name: str) -> Dict[str, str]:
    """Crea una mappa lowercase -> valore originale per una colonna del dataset."""
    df = df_games.copy()
    
    if df.empty or column_name not in df.columns:
        return {}
    
    if column_name == "SubGenres":
        # Per SubGenres, splittiamo i valori separati da virgola
        uniques = set()
        for entry in df[column_name].dropna().astype(str):
            for sub in entry.split("|"):
                uniques.add(sub.strip())
        return {u.lower(): u for u in uniques}
    
    uniques = (
        df[column_name]
        .dropna()
        .astype(str)
        .unique()
    )
    return {u.lower(): u for u in uniques}

VALUE_MAPS: Dict[str, Dict[str, str]] = {
    slot: _build_value_map(col)
    for slot, col in SLOT_TO_COLUMN.items()
}

VALUE_MAPS["age_rating"] = {
    # Target: E (Everyone)
    "e": "E",
    "everyone": "E",
    "kids": "E",
    "child": "E",
    "children": "E",
    "family": "E",
    "family friendly": "E",
    "all ages": "E",
    
    # Target: T (Teen)
    "t": "T",
    "teen": "T",
    "teens": "T",
    "teenager": "T",
    "13+": "T",
    
    # Target: M (Mature)
    "m": "M",
    "mature": "M",
    "adult": "M",
    "adults": "M",
    "18+": "M",
    "violent": "M",
    "blood": "M",
    
    # Target: Unknown / Altro
    "unknown": "Unknown",
    "n/a": "Unknown",
    "?": "Unknown"
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
    if slot_name == "genre" and not matches:
        value_map = VALUE_MAPS.get("subgenre", {})
        keys_extended = list(value_map.keys())
        matches = difflib.get_close_matches(user_norm, keys_extended, n=1, cutoff=0.6)
    if not matches:
        return None

    best_key = matches[0]
    return value_map[best_key]  # valore originale con maiuscole ecc.

def _get_closest_slot(user_input: str) -> Optional[str]:
        """
        Cerca quale slot assomiglia di più all'input dell'utente usando difflib.
        """
        
        # Prendiamo tutte le chiavi (le parole che cerchiamo di matchare)
        possible_matches = list(slot_keywords.keys())
        
        # Normalizziamo l'input utente
        user_norm = user_input.strip().lower()

        # Cerchiamo la corrispondenza più vicina
        # n=1 restituisce solo il migliore, cutoff=0.6 richiede una somiglianza del 60%
        matches = difflib.get_close_matches(user_norm, possible_matches, n=1, cutoff=0.6)

        if matches:
            best_match_key = matches[0]
            # Ritorniamo il nome reale dello slot associato alla chiave trovata
            return slot_keywords[best_match_key]
        
        return None

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
        
    def validate_age_rating(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return self._validate_categorical_from_dataset(
            "age_rating", slot_value, dispatcher, tracker, "utter_age_rating_invalid"
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
        df = df_games.copy()

        if df.empty:
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
        age_rating = tracker.get_slot("age_rating")
        current_page = 1

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
        print("  age_rating:", age_rating)
        print("  page:", current_page)

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
            if df["Genre"].astype(str).str.lower().str.contains(str(genre).lower(), na=False).any():
                df = df[
                df["Genre"]
                .astype(str)
                .str.lower()
                .str.contains(str(genre).lower(), na=False)
            ]
            if df["SubGenres"].astype(str).str.lower().str.contains(str(genre).lower(), na=False).any():
                df = df[
                df["SubGenres"]
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
            
        # Age Rating
        if age_rating not in (None, SKIP_VALUE):
            df = df[
                df["AgeRating"]
                .astype(str)
                .str.strip()
                .str.upper() == str(age_rating).strip().upper()
            ]

        if df.empty:
            return [FollowupAction("utter_no_results")]
        
         # Costruisco la risposta        
        # uso le colonne reali: 'Title', 'Console', 'Genre', 'Usedprice', 'YearReleased'
        cols = ["Title", "Console", "Genre", "US Sales (millions)", "Review Score", "Usedprice", "YearReleased"]
        missing = [c for c in cols if c not in df.columns]
        if missing:
            dispatcher.utter_message(
            text=f"Internal error: expected columns {missing} not found in dataset."
            )
            return []

        all_recommended_games = df[cols].head(100)
        
        page_size = 5
        
        # Calcolo indici e totali
        total_items = len(all_recommended_games)
        total_pages = math.ceil(total_items / page_size)
        
        recommended_games = all_recommended_games.head(page_size)
        
        if recommended_games.empty:
            return [FollowupAction("utter_no_more_results")]
        
        message_lines = [
            f"Page 1 of {total_pages}",
            "Here are some game recommendations for you:",
        ]
        for _, row in recommended_games.iterrows():
            title = row["Title"]
            cons = row["Console"]
            gen = row["Genre"]
            sales = row["US Sales (millions)"]
            score = row["Review Score"]
            price = row["Usedprice"]
            year = int(row["YearReleased"]) if not pd.isna(row["YearReleased"]) else "N/A"

            message_lines.append(
                    f"------------------------------\n"
                    f"🎮 **{title}**\n"
                    f"🕹️ Console: {cons}\n"
                    f"📅 Year: {year} | ⭐ Score: {score}\n"
                    f"🎭 Genre: {gen}\n"
                    f"🏆 Sales: {sales} million\n"
                    f"💰 Used Price: {price}"
                )
            
        if total_pages > 1:
            message_lines.append("\nType **'next'** to see more results ➡️")
            
        dispatcher.utter_message(text="\n".join(message_lines))

        return [
            SlotSet("last_result", all_recommended_games[["Title", "Console", "US Sales (millions)", "Review Score", "Genre", "Usedprice", "YearReleased"]].to_dict(orient='records')),
            SlotSet("page", current_page)
            ]

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
            "age_rating",
            "page"
        ]

        
        dispatcher.utter_message(response="utter_reset_preferences")

        return [SlotSet(slot, None) for slot in slots_to_reset]
    
class ActionRelaxFilters(Action):

    def name(self) -> Text:
        return "action_relax_filters"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        slots_to_relax_input = tracker.get_slot("filters_to_relax")
        
        # Gestione input sia come lista che come stringa singola
        if isinstance(slots_to_relax_input, str):
            # Se è una stringa con virgole (es. "price, genre"), la dividiamo
            input_list = [s.strip() for s in slots_to_relax_input.split(",")]
        else:
            input_list = slots_to_relax_input

        events = []
        relaxed_filters_display = []

        for raw_filter in input_list:
            # Usiamo la funzione fuzzy per trovare lo slot
            target_slot = _get_closest_slot(raw_filter)

            if target_slot:
                # Impostiamo lo slot a None
                events.append(SlotSet(target_slot, None))
                relaxed_filters_display.append(target_slot.replace("_", " ")) # Solo per bellezza nel messaggio
            else:
                dispatcher.utter_message(text=f"Sorry, I couldn't identify the filter: {raw_filter}")
                pass

        if relaxed_filters_display:
            msg = f"Ok, I've removed the filters for: {', '.join(relaxed_filters_display)}."
            dispatcher.utter_message(text=msg)
            # Resettiamo lo slot che contiene la richiesta, per pulizia
            events.append(SlotSet("filters_to_relax", None))
        else:
            dispatcher.utter_message(text="I couldn't identify any valid filters to relax from your request.")

        return events

class ActionShowBestSellers(Action):
    def name(self) -> Text:
        return "action_show_best_sellers"

    def run(self, dispatcher, tracker, domain):
        sales_col = "US Sales (millions)" 
        df = df_games.copy()
        page_size = 5
        
        if sales_col not in df.columns:
            dispatcher.utter_message(text="Sorry, I don't have sales data available.")
            return []
        
        # Ordina per vendite decrescenti e prendi i primi 5
        all_top_sellers = df.sort_values(by=sales_col, ascending=False).head(100)
        
        total_items = len(all_top_sellers)
        total_pages = math.ceil(total_items / page_size)
        
        top_sellers = all_top_sellers.head(page_size)
        
        message_blocks = [
            f"Page 1 of {total_pages}",
            "Here are the best-selling games of all time in my archive: 🏆"
        ]
        for _, row in top_sellers.iterrows():
            title = row["Title"]
            cons = row["Console"]
            sold = row[sales_col]
            score = row["Review Score"]
            genre = row["Genre"]
            price = row["Usedprice"]
            year = int(row["YearReleased"]) if not pd.isna(row["YearReleased"]) else "N/A"

            message_blocks.append(
                    f"------------------------------\n"
                    f"🎮 **{title}**\n"
                    f"🕹️ Console: {cons}\n"
                    f"📅 Year: {year} | ⭐ Score: {score}\n"
                    f"🎭 Genre: {genre}\n"
                    f"🏆 Sales: {sold} million\n"
                    f"💰 Used Price: {price}"
                )
        
        if total_pages > 1:
            message_blocks.append("\nType **'next'** to see more results ➡️")

        dispatcher.utter_message(text="\n".join(message_blocks))
            
        return [
            SlotSet("last_result", all_top_sellers[["Title", "Console", "Genre", sales_col, "Review Score", "Usedprice", "YearReleased"]].to_dict(orient='records')),
            SlotSet("page", 1)            
            ]

class ActionShowHighestRated(Action):
    def name(self) -> Text:
        return "action_show_highest_rated"

    def run(self, dispatcher, tracker, domain):
        score_col = "Review Score"
        page_size = 5
        df = df_games.copy()
        
        if score_col not in df.columns:
            dispatcher.utter_message(text="Sorry, review data is missing.")
            return []
                
        # Ordina per punteggio decrescente
        all_top_rated = df.sort_values(by=score_col, ascending=False).head(100)
        
        total_items = len(all_top_rated)
        total_pages = math.ceil(total_items / page_size)
        
        top_rated = all_top_rated.head(page_size)

        message_blocks = [
            f"Page 1 of {total_pages}",
            "Here are the critically acclaimed masterpieces: ⭐"
        ]
        for _, row in top_rated.iterrows():
            title = row["Title"]
            cons = row["Console"]
            genre = row["Genre"]
            sold = row["US Sales (millions)"]
            score = row[score_col]
            price = row["Usedprice"]
            year = int(row["YearReleased"]) if not pd.isna(row["YearReleased"]) else "N/A"

            message_blocks.append(
                    f"------------------------------\n"
                    f"🎮 **{title}**\n"
                    f"🕹️ Console: {cons}\n"
                    f"📅 Year: {year} | ⭐ Score: {score}\n"
                    f"🎭 Genre: {genre}\n"
                    f"🏆 Sales: {sold} million\n"
                    f"💰 Used Price: {price}"
                )
        
        if total_pages > 1:
            message_blocks.append("\nType **'next'** to see more results ➡️")

        dispatcher.utter_message(text="\n".join(message_blocks))

        return [
            SlotSet("last_result", all_top_rated[["Title", "Console", "Genre", "US Sales (millions)", score_col, "Usedprice", "YearReleased"]].to_dict(orient='records')),
            SlotSet("page", 1)            
            ]
    
class ActionSaveGame(Action):
    def name(self) -> Text:
        return "action_save_game"

    def run(self, dispatcher, tracker, domain):
        # 1. Recupera il titolo detto dall'utente
        game_input = tracker.get_slot("game_title_to_save")
        df = df_games.copy()
        
        # Se l'utente non ha specificato il titolo (ha attivato l'intent senza entità)
        if not game_input:
            dispatcher.utter_message(text="Which game would you like to save?")
            return []

        # 2. Cerca il gioco nel database usando difflib (Fuzzy Search)
        all_titles = df['Title'].astype(str).unique().tolist()
        matches = difflib.get_close_matches(game_input, all_titles, n=1, cutoff=0.6)

        if not matches:
            dispatcher.utter_message(text=f"I couldn't find a game named '{game_input}' in my database.")
            return [SlotSet("game_title_to_save", None)]

        found_game = matches[0]

        # 3. Gestisci la lista dei salvati
        current_saved = tracker.get_slot("saved_games")
        if not current_saved:
            current_saved = []

        if found_game in current_saved:
            dispatcher.utter_message(text=f"'{found_game}' is already in your list! ✅")
        else:
            current_saved.append(found_game)
            dispatcher.utter_message(text=f"Saved '{found_game}' to your favorites! 💾")

        # Aggiorna lo slot della lista e pulisce lo slot temporaneo di input
        return [
            SlotSet("saved_games", current_saved),
            SlotSet("game_title_to_save", None)
        ]

class ActionDeleteSavedGame(Action):
    def name(self) -> Text:
        return "action_delete_saved_game"

    def run(self, dispatcher, tracker, domain):
        game_input = tracker.get_slot("game_title_to_delete")
        
        if not game_input:
            dispatcher.utter_message(text="Which game would you like to delete from your saved list?")
            return []

        current_saved = tracker.get_slot("saved_games")
        if not current_saved:
            dispatcher.utter_message(text="Your saved games list is empty.")
            return [SlotSet("game_title_to_delete", None)]

        matches = difflib.get_close_matches(game_input, current_saved, n=1, cutoff=0.6)

        if not matches:
            dispatcher.utter_message(text=f"'{game_input}' is not in your saved list.")
            return [SlotSet("game_title_to_delete", None)]

        game_to_delete = matches[0]
        current_saved.remove(game_to_delete)
        dispatcher.utter_message(text=f"Removed '{game_to_delete}' from your saved games. 🗑️")

        return [
            SlotSet("saved_games", current_saved),
            SlotSet("game_title_to_delete", None)
        ]

class ActionShowSavedGames(Action):
    def name(self) -> Text:
        return "action_show_saved_games"

    def run(self, dispatcher, tracker, domain):
        saved_list = tracker.get_slot("saved_games")

        if not saved_list:
            dispatcher.utter_message(text="Your list is empty. Ask me to save a game first!")
        else:
            msg = "Here are your saved games: 📝\n" + "\n".join([f"- {g}" for g in saved_list])
            dispatcher.utter_message(text=msg)
            
        return []
    
class ActionNextPage(Action):
    def name(self) -> Text:
        return "action_next_page"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        last_results = tracker.get_slot("last_result")
        current_page = tracker.get_slot("page") or 1
        page_size = 5

        if not last_results:
            dispatcher.utter_message(text="There are no previous results to show.")
            return []
        
        # Calcolo indici e totali
        total_items = len(last_results)
        total_pages = math.ceil(total_items / page_size)
        
        start_index = current_page * page_size
        end_index = start_index + page_size

        # Se siamo andati oltre la fine della lista
        if start_index >= total_items:
            dispatcher.utter_message(text="You've reached the end of the list! 🏁")
            # Opzionale: Resetta la pagina a 1 se vuoi ricominciare o lascia così
            return [SlotSet("page", 1)]

        # Calcola gli indici per la pagina successiva
        page_results = last_results[start_index:end_index]

        if not page_results:
            dispatcher.utter_message(text="No more results available.")
            return []
        
        page_to_show = current_page + 1

        message_blocks = [f"📄 **Page {page_to_show} of {total_pages}**"]
        for game in page_results:
            if isinstance(game, dict):
                title = game.get('Title', 'Unknown')
                console = game.get('Console', 'N/A')
                genre = game.get('Genre', 'N/A')
                sales = game.get('US Sales (millions)', 'N/A')
                price = game.get('Usedprice', 'N/A')
                score = game.get('Review Score', 'N/A')
                year = game.get('YearReleased', 'N/A')
                
                # Formattazione a blocco con Emoji
                block = (
                    f"------------------------------\n"
                    f"🎮 **{title}**\n"
                    f"🕹️ Console: {console}\n"
                    f"📅 Year: {year} | ⭐ Score: {score}\n"
                    f"🎭 Genre: {genre}\n"
                    f"🏆 Sales: {sales} million\n"
                    f"💰 Used Price: {price}"
                )
                message_blocks.append(block)
            else:
                # Fallback se per caso i dati sono solo stringhe
                message_blocks.append(f"- {game}")
                
        # Footer con suggerimento
        if page_to_show < total_pages:
            message_blocks.append("\nType **'next'** to see more results ➡️")
        else:
            message_blocks.append("\nThis was the last page. ✅")

        dispatcher.utter_message(text="\n".join(message_blocks))

        return [SlotSet("page", current_page + 1)]
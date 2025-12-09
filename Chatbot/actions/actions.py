from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

import pandas as pd

# Carico il dataset una volta sola all'avvio dell'action server
df_games = pd.DataFrame()
try:
    df_games = pd.read_csv("./dataset/vintage_games_clean.csv")
    print("Loaded games dataset with columns:", df_games.columns.tolist())
except FileNotFoundError:
    print("vintage_games_clean.csv file not found. Check the path!")
    pass


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

        print("[action_search_game] Slots:")
        print("  console:", console)
        print("  genre:", genre)
        print("  used_price:", used_price)
        print("  release_year:", release_year)
        print("  review_score:", review_score)
        print("  max_player:", max_player)
        print("  online:", online)
        print("  multiplatform:", multiplatform)

        df = df_games.copy()

        # ✅ FILTRI: usa i nomi delle colonne REALI del CSV

        # Console (colonna 'Console')
        if console:
            df = df[
                df["Console"]
                .astype(str)
                .str.lower()
                .str.contains(str(console).lower(), na=False)
            ]

        # Genere principale (colonna 'Genre')
        if genre:
            df = df[
                df["Genre"]
                .astype(str)
                .str.lower()
                .str.contains(str(genre).lower(), na=False)
            ]

        # Anno di uscita (colonna 'YearReleased')
        if release_year is not None:
            try:
                year = int(release_year)
                df = df[df["YearReleased"] == year]
            except (ValueError, TypeError):
                pass

        # Prezzo usato (colonna 'Usedprice')
        if used_price is not None:
            try:
                max_price = float(used_price)
                df = df[df["Usedprice"] <= max_price]
            except (ValueError, TypeError):
                # Se non si riesce a convertire, ignora il filtro
                pass

        # Review score minimo (colonna 'Review Score')
        if review_score is not None:
            try:
                min_score = float(review_score)
                df = df[df["Review Score"] >= min_score]
            except (ValueError, TypeError):
                pass

        # Numero massimo giocatori (colonna 'MaxPlayers')
        if max_player is not None:
            try:
                max_p = int(max_player)
                df = df[df["MaxPlayers"] <= max_p]
            except (ValueError, TypeError):
                pass

        # Online (colonna 'Online' 0/1) – interpreta lo slot come preferenza
        if online is not None:
            v = str(online).strip().lower()
            if v in {"yes", "y", "true", "online"}:
                df = df[df["Online"] == 1]
            elif v in {"no", "n", "false", "offline"}:
                df = df[df["Online"] == 0]

        # Multiplatform (colonna 'Multiplatform' 0/1)
        if multiplatform is not None:
            v = str(multiplatform).strip().lower()
            if v in {"multiplatform", "multi", "yes", "true"}:
                df = df[df["Multiplatform"] == 1]
            elif v in {"exclusive", "single", "no", "false"}:
                df = df[df["Multiplatform"] == 0]

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

            recommended_games = df[cols].head(5)

            message_lines = ["Here are some game recommendations for you:"]
            for _, row in recommended_games.iterrows():
                title = row["Title"]
                cons = row["Console"]
                gen = row["Genre"]
                price = row["Usedprice"]
                year = int(row["YearReleased"]) if not pd.isna(row["YearReleased"]) else "N/A"

                message_lines.append(
                    f"- {title} ({cons}, {gen}, ${price}, {year})"
                )
                shown_result.append(title)

            dispatcher.utter_message(text="\n".join(message_lines))

        return [SlotSet("last_result", shown_result)]

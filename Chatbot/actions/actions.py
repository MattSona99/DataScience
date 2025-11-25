# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
# from rasa_sdk import Action, Tracker
# from rasa_sdk.executor import CollectingDispatcher
#
#
# class ActionHelloWorld(Action):
#
#     def name(self) -> Text:
#         return "action_hello_world"
#
#     def run(self, dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
#         dispatcher.utter_message(text="Hello World!")
#
# #         return []

from tkinter import EventType
from typing import Any, Text, Dict, List, Optional
from rasa_sdk import Action, Tracker
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import pandas as pd

df_games = pd.DataFrame()
try:
    df_games = pd.read_csv('Chatbot/dataset/vintage_games_clean.csv')
except FileNotFoundError:
    print("games.csv file not found. Make sure the file exists in the specified path.")
    pass

class ActionSearchGame(Action):

    def name(self) -> Text:
        return "action_search_game"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if df_games.empty:
            dispatcher.utter_message(text="Sorry, the game database is not available.")
            return []
        
        # Estract user preferences from slots
        console = tracker.get_slot('console')
        genre = tracker.get_slot('genre')
        used_price = tracker.get_slot('used_price')
        release_year = tracker.get_slot('release_year')
        review_score = tracker.get_slot('review_score')
        max_player = tracker.get_slot('max_player')
        online = tracker.get_slot('online')
        multiplayer = tracker.get_slot('multiplayer')          

        # Implement your custom action logic here
        dispatcher.utter_message(text="Searching for the game...")
        
        df = df_games.copy()
        if console:
            df = df[df['console'].str.lower().str.contains(console.lower(), case=False, na=False)]
        if genre:
            df = df[df['genre'].str.lower().str.contains(genre.lower(), case=False, na=False)]
        if used_price:
            df = df[df['used_price'] <= float(used_price)]
        if release_year:
            df = df[df['release_year'] == int(release_year)]
        if review_score:
            df = df[df['review_score'] >= float(review_score)]
        if max_player:
            df = df[df['max_player'] >= int(max_player)]
        if online:
            df = df[df['online'] == online]
        if multiplayer:
            df = df[df['multiplayer'] == multiplayer]
            
        shown_result = []
        if df.empty:
            dispatcher.utter_message(text="Sorry, no game found.")
        else:
            recommended_games = df[['name', 'console', 'genre', 'used_price', 'release_year']].head(5)
            message = "Here are some game recommendations for you:\n"
            for index, row in recommended_games.iterrows():
                message += f"- {row['name']} ({row['console']}, {row['genre']}, ${row['used_price']}, {row['release_year']})\n"
                shown_result.append(row['name'])
            dispatcher.utter_message(text=message)
              
        return [SlotSet("last_result", shown_result)]
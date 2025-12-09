# components/lowercase.py

from __future__ import annotations
from typing import Dict, Text, Any

from rasa.engine.graph import GraphComponent, ExecutionContext
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.nlu.training_data.message import Message

class LowercasePreprocessor(GraphComponent):
    """Trasforma tutto il testo in lowercase."""

    @staticmethod
    def get_default_config() -> Dict[Text, Any]:
        return {}

    def __init__(self, config: Dict[Text, Any]) -> None:
        self._config = config

    @classmethod
    def create(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> GraphComponent:
        return cls(config)

    def process(self, message: Message) -> Message:
        text = message.get("text")
        if text:
            message.set("text", text.lower())
        return message

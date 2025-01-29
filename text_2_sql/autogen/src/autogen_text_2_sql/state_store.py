from abc import ABC, abstractmethod
from cachetools import TTLCache


class StateStore(ABC):
    @abstractmethod
    def get_state(self, thread_id):
        pass

    @abstractmethod
    def save_state(self, thread_id, state):
        pass


class InMemoryStateStore(StateStore):
    def __init__(self):
        self.cache = TTLCache(maxsize=1000, ttl=4 * 60 * 60)  # 4 hours

    def get_state(self, thread_id: str) -> dict:
        return self.cache.get(thread_id)

    def save_state(self, thread_id: str, state: dict) -> None:
        self.cache[thread_id] = state

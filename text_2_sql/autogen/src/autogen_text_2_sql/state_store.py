from abc import ABC, abstractmethod

class StateStore(ABC):
    @abstractmethod
    def get_state(self, thread_id):
        pass

    @abstractmethod
    def save_state(self, thread_id, state):
        pass


class InMemoryStateStore(StateStore):
    def __init__(self):
        # Replace with a caching library or something to have some sort of expiry for entries so this doesn't grow forever
        self.cache = {}

    def get_state(self, thread_id):
        return self.cache.get(thread_id)

    def save_state(self, thread_id, state):
        self.cache[thread_id] = state

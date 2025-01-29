from abc import ABC, abstractmethod
from cachetools import TTLCache
from azure.cosmos import CosmosClient, exceptions


class StateStore(ABC):
    @abstractmethod
    def get_state(self, thread_id: str) -> dict:
        pass

    @abstractmethod
    def save_state(self, thread_id: str, state: dict) -> None:
        pass


class InMemoryStateStore(StateStore):
    def __init__(self):
        self.cache = TTLCache(maxsize=1000, ttl=4 * 60 * 60)  # 4 hours

    def get_state(self, thread_id: str) -> dict:
        return self.cache.get(thread_id)

    def save_state(self, thread_id: str, state: dict) -> None:
        self.cache[thread_id] = state


class CosmosStateStore(StateStore):
    def __init__(self, endpoint, database, container, credential, partition_key=None):
        client = CosmosClient(url=endpoint, credential=credential)
        database_client = client.get_database_client(database)
        self._db = database_client.get_container_client(container)
        self.partition_key = partition_key

        # Set partition key field name
        props = self._db.read()
        pk_paths = props["partitionKey"]["paths"]
        if len(pk_paths) != 1:
            raise ValueError("Only single partition key is supported")
        self.partition_key_name = pk_paths[0].lstrip("/")
        if "/" in self.partition_key_name:
            raise ValueError("Only top-level partition key is supported")

    def get_state(self, thread_id: str) -> dict:
        try:
            item = self._db.read_item(item=thread_id, partition_key=self.partition_key)
            return item["state"]
        except exceptions.CosmosResourceNotFoundError:
            return None

    def save_state(self, thread_id: str, state: dict) -> None:
        self._db.upsert_item(
            body={
                self.partition_key_name: self.partition_key,
                "id": thread_id,
                "state": state,
            }
        )

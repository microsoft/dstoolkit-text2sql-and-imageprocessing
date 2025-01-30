from enum import Enum, auto

class DatabaseEngine(Enum):
    """Enum for supported database engines."""
    TSQL = "tsql"
    SQLITE = "sqlite"

class DatabaseEngineSpecificFields(Enum):
    """Enum for database engine specific fields."""
    TSQL_SCHEMA = "Schema"
    TSQL_DEFINITION = "Definition"
    TSQL_SAMPLE_VALUES = "SampleValues"
    SQLITE_SCHEMA = "Schema"
    SQLITE_DEFINITION = "Definition"
    SQLITE_SAMPLE_VALUES = "SampleValues"

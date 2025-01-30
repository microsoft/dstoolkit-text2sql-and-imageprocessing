from enum import Enum, auto

class DatabaseEngine(Enum):
    """Enum for supported database engines."""
    TSQL = "tsql"
    SQLITE = "sqlite"

<<<<<<< HEAD
class DatabaseEngineSpecificFields(Enum):
    """Enum for database engine specific fields."""
    TSQL_SCHEMA = "Schema"
    TSQL_DEFINITION = "Definition"
    TSQL_SAMPLE_VALUES = "SampleValues"
    SQLITE_SCHEMA = "Schema"
    SQLITE_DEFINITION = "Definition"
    SQLITE_SAMPLE_VALUES = "SampleValues"
=======
class DatabaseEngine(StrEnum):
    """An enumeration to represent a database engine."""

    DATABRICKS = "DATABRICKS"
    SNOWFLAKE = "SNOWFLAKE"
    TSQL = "TSQL"
    POSTGRESQL = "POSTGRESQL"
    SQLITE = "SQLITE"


class DatabaseEngineSpecificFields(StrEnum):
    """An enumeration to represent the database engine specific fields."""

    WAREHOUSE = "Warehouse"
    DATABASE = "Database"
    CATALOG = "Catalog"
>>>>>>> upstream/main

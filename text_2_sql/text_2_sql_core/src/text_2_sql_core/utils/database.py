from enum import StrEnum


class DatabaseEngine(StrEnum):
    """An enumeration to represent a database engine."""

    DATABRICKS = "DATABRICKS"
    SNOWFLAKE = "SNOWFLAKE"
    TSQL = "TSQL"
    POSTGRES = "POSTGRES"
    SQLITE = "SQLITE"


class DatabaseEngineSpecificFields(StrEnum):
    """An enumeration to represent the database engine specific fields."""

    WAREHOUSE = "Warehouse"
    DATABASE = "Database"
    CATALOG = "Catalog"

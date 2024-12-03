from enum import StrEnum


class DatabaseEngine(StrEnum):
    """An enumeration to represent a database engine."""

    SNOWFLAKE = "SNOWFLAKE"
    TSQL = "TSQL"
    DATABRICKS = "DATABRICKS"

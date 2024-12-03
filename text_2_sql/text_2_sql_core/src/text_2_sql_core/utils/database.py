from enum import StrEnum


class DatabaseEngine(StrEnum):
    """An enumeration to represent a database engine."""

    DATABRICKS = "DATABRICKS"
    SNOWFLAKE = "SNOWFLAKE"
    TSQL = "TSQL"

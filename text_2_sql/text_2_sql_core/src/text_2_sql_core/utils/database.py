from enum import StrEnum


class DatabaseEngine(StrEnum):
    """An enumeration to represent a database engine."""

    DATABRICKS = "DATABRICKS"
    SNOWFLAKE = "SNOWFLAKE"
    TSQL = "TSQL"
    POSTGRESQL = "POSTGRESQL"
    SQLITE = "SQLITE"


class DatabaseEngineSpecificFields(StrEnum):
    """An enumeration to represent the database engine specific fields."""

    # Connection fields
    WAREHOUSE = "Warehouse"
    DATABASE = "Database"
    CATALOG = "Catalog"

    # Schema fields
    TSQL_SCHEMA = "Schema"
    TSQL_DEFINITION = "Definition"
    TSQL_SAMPLE_VALUES = "SampleValues"
    SQLITE_SCHEMA = "Schema"
    SQLITE_DEFINITION = "Definition"
    SQLITE_SAMPLE_VALUES = "SampleValues"
    POSTGRESQL_SCHEMA = "Schema"
    POSTGRESQL_DEFINITION = "Definition"
    POSTGRESQL_SAMPLE_VALUES = "SampleValues"
    DATABRICKS_SCHEMA = "Schema"
    DATABRICKS_DEFINITION = "Definition"
    DATABRICKS_SAMPLE_VALUES = "SampleValues"
    SNOWFLAKE_SCHEMA = "Schema"
    SNOWFLAKE_DEFINITION = "Definition"
    SNOWFLAKE_SAMPLE_VALUES = "SampleValues"

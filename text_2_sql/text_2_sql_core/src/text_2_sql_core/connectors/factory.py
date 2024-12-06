import os


class ConnectorFactory:
    @staticmethod
    def get_database_connector():
        try:
            if os.environ["Text2Sql__DatabaseEngine"].upper() == "DATABRICKS":
                from text_2_sql_core.connectors.databricks_sql import (
                    DatabricksSqlConnector,
                )

                return DatabricksSqlConnector()
            elif os.environ["Text2Sql__DatabaseEngine"].upper() == "SNOWFLAKE":
                from text_2_sql_core.connectors.snowflake_sql import (
                    SnowflakeSqlConnector,
                )

                return SnowflakeSqlConnector()
            elif os.environ["Text2Sql__DatabaseEngine"].upper() == "TSQL":
                from text_2_sql_core.connectors.tsql_connector import TSQLConnector

                return TSQLConnector()
            else:
                raise ValueError(
                    f"""Database engine {
                    os.environ['Text2Sql__DatabaseEngine']} not found"""
                )
        except ImportError:
            raise ValueError(
                f"""Failed to import {
                os.environ['Text2Sql__DatabaseEngine']} SQL Connector. Check you have installed the optional dependencies for this database engine."""
            )

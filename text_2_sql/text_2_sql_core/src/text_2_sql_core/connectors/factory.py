# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
from text_2_sql_core.connectors.ai_search import AISearchConnector
from text_2_sql_core.connectors.open_ai import OpenAIConnector


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
                from text_2_sql_core.connectors.tsql_sql import TsqlSqlConnector

                return TsqlSqlConnector()
            elif os.environ["Text2Sql__DatabaseEngine"].upper() == "POSTGRESQL":
                from text_2_sql_core.connectors.postgresql_sql import (
                    PostgresqlSqlConnector,
                )

                return PostgresqlSqlConnector()
            elif os.environ["Text2Sql__DatabaseEngine"].upper() == "SQLITE":
                from text_2_sql_core.connectors.sqlite_sql import SQLiteSqlConnector

                return SQLiteSqlConnector()
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

    @staticmethod
    def get_ai_search_connector():
        # Return None if AI Search is disabled
        if os.environ.get("Text2Sql__UseAISearch", "True").lower() != "true":
            return None
        return AISearchConnector()

    @staticmethod
    def get_open_ai_connector():
        return OpenAIConnector()

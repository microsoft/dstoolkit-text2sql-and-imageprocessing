# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import sqlite3
import logging
from typing import Annotated
import json
import re

from text_2_sql_core.utils.database import DatabaseEngine
from text_2_sql_core.connectors.sql import SqlConnector


class SQLiteSqlConnector(SqlConnector):
    def __init__(self):
        super().__init__()
        self.database_engine = DatabaseEngine.SQLITE

    def engine_specific_rules(self) -> list[str]:
        """Get SQLite specific rules.

        Returns:
            list[str]: List of SQLite specific rules.
        """
        return [
            "Use SQLite syntax for queries",
            "Use double quotes for identifiers",
            "Use single quotes for string literals",
            "LIMIT clause comes after ORDER BY",
            "No FULL OUTER JOIN support - use LEFT JOIN or RIGHT JOIN instead",
            "Use || for string concatenation",
            "Use datetime('now') for current timestamp",
            "Use strftime() for date/time formatting",
        ]

    @property
    def invalid_identifiers(self) -> list[str]:
        """Get the invalid identifiers upon which a sql query is rejected."""
        return []  # SQLite has no reserved words that conflict with our use case

    @property
    def engine_specific_fields(self) -> list[str]:
        """Get the engine specific fields."""
        return []  # SQLite doesn't use warehouses, catalogs, or separate databases

    async def query_execution(
        self,
        sql_query: Annotated[
            str,
            "The SQL query to run against the database.",
        ],
        cast_to: any = None,
        limit=None,
    ) -> list[dict]:
        """Run the SQL query against the database.

        Args:
            sql_query: The SQL query to execute.
            cast_to: Optional type to cast results to.
            limit: Optional limit on number of results.

        Returns:
            List of dictionaries containing query results.
        """
        db_file = os.environ["Text2Sql__Tsql__ConnectionString"]

        if not os.path.exists(db_file):
            raise FileNotFoundError(f"Database file not found: {db_file}")

        logging.info(f"Running query against {db_file}: {sql_query}")

        results = []
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(sql_query)

            columns = (
                [column[0] for column in cursor.description]
                if cursor.description
                else []
            )

            if limit is not None:
                rows = cursor.fetchmany(limit)
            else:
                rows = cursor.fetchall()

            for row in rows:
                if cast_to:
                    results.append(cast_to.from_sql_row(row, columns))
                else:
                    results.append(dict(zip(columns, row)))

        logging.debug("Results: %s", results)
        return results

    def normalize_term(self, term: str) -> str:
        """Normalize a term for matching by:
        1. Converting to lowercase
        2. Removing underscores and spaces
        3. Removing trailing 's' for plurals
        4. Removing common prefixes/suffixes
        """
        term = term.lower()
        term = re.sub(r"[_\s]+", "", term)
        term = re.sub(r"s$", "", term)  # Remove trailing 's' for plurals
        return term

    def terms_match(self, term1: str, term2: str) -> bool:
        """Check if two terms match after normalization."""
        normalized1 = self.normalize_term(term1)
        normalized2 = self.normalize_term(term2)
        logging.debug(
            f"Comparing normalized terms: '{normalized1}' and '{normalized2}'"
        )
        return normalized1 == normalized2

    def find_matching_tables(self, text: str, table_names: list[str]) -> list[int]:
        """Find all matching table indices using flexible matching rules.

        Args:
            text: The search term
            table_names: List of table names to search

        Returns:
            List of matching table indices
        """
        matches = []
        logging.info(
            "Looking for tables matching '%s' in tables: %s", text, table_names
        )

        # First try exact matches
        for idx, name in enumerate(table_names):
            if self.terms_match(text, name):
                logging.info(f"Found exact match: '{name}'")
                matches.append(idx)

        if matches:
            return matches

        # Try matching parts of compound table names
        search_terms = set(re.split(r"[_\s]+", text.lower()))
        logging.info(f"Trying partial matches with terms: {search_terms}")
        for idx, name in enumerate(table_names):
            table_terms = set(re.split(r"[_\s]+", name.lower()))
            if search_terms & table_terms:  # If there's any overlap in terms
                logging.info(
                    "Found partial match: '%s' with terms %s", name, table_terms
                )
                matches.append(idx)

        return matches

    async def get_entity_schemas(
        self,
        text: Annotated[
            str,
            "The text to run a semantic search against. Relevant entities will be returned.",
        ],
        excluded_entities: Annotated[
            list[str],
            "The entities to exclude from the search results.",
        ] = [],
        as_json: bool = True,
    ) -> str:
        """Gets the schema of a view or table in the SQLite database.

        Args:
            text: The text to search against.
            excluded_entities: Entities to exclude from results.
            as_json: Whether to return results as JSON string.

        Returns:
            Schema information as JSON string or list of dictionaries.
        """
        # Load Spider schema file using SPIDER_DATA_DIR environment variable
        schema_file = os.path.join(os.environ["SPIDER_DATA_DIR"], "tables.json")

        if not os.path.exists(schema_file):
            raise FileNotFoundError(f"Schema file not found: {schema_file}")

        with open(schema_file) as f:
            spider_schemas = json.load(f)

        # Get current database name from path
        db_path = os.environ["Text2Sql__Tsql__ConnectionString"]
        db_name = os.path.splitext(os.path.basename(db_path))[0]

        logging.info(f"Looking for schemas in database: {db_name}")

        # Find schema for current database
        db_schema = None
        for schema in spider_schemas:
            if schema["db_id"] == db_name:
                db_schema = schema
                break

        if not db_schema:
            raise ValueError(f"Schema not found for database: {db_name}")

        logging.info("Looking for tables matching '%s' in database '%s'", text, db_name)
        logging.info(f"Available tables: {db_schema['table_names']}")

        # Find all matching tables using flexible matching
        table_indices = self.find_matching_tables(text, db_schema["table_names"])

        if not table_indices:
            logging.warning(f"No tables found matching: {text}")
            return [] if not as_json else "[]"

        logging.info(f"Found matching table indices: {table_indices}")

        # Get schemas for all matching tables
        schemas = []
        for table_idx in table_indices:
            # Get columns for this table
            columns = []
            for j, (t_idx, c_name) in enumerate(db_schema["column_names"]):
                if t_idx == table_idx:
                    columns.append(
                        {
                            "Name": db_schema["column_names_original"][j][1],
                            "Type": db_schema["column_types"][j],
                        }
                    )

            schema = {
                "SelectFromEntity": db_schema["table_names"][table_idx],
                "Columns": columns,
            }
            schemas.append(schema)
            logging.info(
                "Added schema for table '%s': %s",
                db_schema["table_names"][table_idx],
                schema,
            )

        if as_json:
            return json.dumps(schemas, default=str)
        else:
            return schemas

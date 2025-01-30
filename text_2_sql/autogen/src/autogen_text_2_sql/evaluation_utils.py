# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import re
import logging
from typing import Optional, List, Dict, Any, Tuple


def normalize_query(query: str) -> str:
    """
    Normalize a SQL query by cleaning whitespace and standardizing case for keywords.
    Preserves case for table and column names.

    Args:
        query: SQL query to normalize

    Returns:
        Normalized query
    """
    if not query or query == "SELECT NULL -- No query found":
        return query

    # Clean whitespace
    query = " ".join(query.split())

    # Find all quoted strings and table/column identifiers to preserve their case
    preserved = {}
    counter = 0

    # Save quoted strings
    for match in re.finditer(r"'[^']*'|\"[^\"]*\"", query):
        placeholder = f"__QUOTED_{counter}__"
        preserved[placeholder] = match.group(0)
        query = query.replace(match.group(0), placeholder)
        counter += 1

    # Save table and column names (assuming they're between spaces, dots, or parentheses)
    for match in re.finditer(r"(?<=[\s.(])[A-Za-z_][A-Za-z0-9_]*(?=[\s.)])", query):
        if match.group(0).upper() not in {
            "SELECT",
            "FROM",
            "WHERE",
            "JOIN",
            "ON",
            "GROUP",
            "BY",
            "HAVING",
            "ORDER",
            "LIMIT",
            "OFFSET",
            "AND",
            "OR",
            "NOT",
            "IN",
            "EXISTS",
            "COUNT",
            "SUM",
            "AVG",
            "MIN",
            "MAX",
            "AS",
            "DISTINCT",
        }:
            placeholder = f"__IDENT_{counter}__"
            preserved[placeholder] = match.group(0)
            query = query.replace(match.group(0), placeholder)
            counter += 1

    # Uppercase SQL keywords
    query = re.sub(
        r"\b(SELECT|FROM|WHERE|JOIN|ON|GROUP|BY|HAVING|ORDER|LIMIT|OFFSET|AND|OR|NOT|IN|EXISTS|COUNT|SUM|AVG|MIN|MAX|AS|DISTINCT)\b",
        lambda m: m.group(0).upper(),
        query,
        flags=re.IGNORECASE,
    )

    # Restore preserved strings and identifiers
    for placeholder, original in preserved.items():
        query = query.replace(placeholder, original)

    return query


def extract_sql_queries_from_results(results: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Extract SQL queries and their database IDs from the results dictionary.

    Args:
        results: Dictionary containing query results

    Returns:
        List of tuples (query, database_id)
    """
    queries = []

    if results.get("contains_database_results") and results.get("database_results"):
        for question_results in results["database_results"].values():
            for result in question_results:
                if isinstance(result, dict):
                    query = result.get("sql_query", "").strip()
                    db_id = result.get("database_id", "")
                    if query and query != "SELECT NULL -- No query found":
                        queries.append((normalize_query(query), db_id))

    return queries


def extract_sql_queries_from_logs(log_text: str) -> List[Tuple[str, str]]:
    """
    Extract SQL queries and their database IDs from the autogen logs.

    Args:
        log_text: The log text containing SQL queries

    Returns:
        List of tuples (query, database_id)
    """
    queries = []
    current_db = ""

    # Extract current database from log messages
    db_matches = re.finditer(r"Processing query \d+/\d+ for database (\w+)", log_text)
    for match in db_matches:
        current_db = match.group(1)

    # Pattern 1: Look for queries after "Running query against"
    running_pattern = r"Running query against.*?: (SELECT.*?)(?=\n|$)"
    running_matches = re.finditer(running_pattern, log_text, re.IGNORECASE)
    for match in running_matches:
        query = match.group(1).strip()
        if query and query != "SELECT NULL -- No query found":
            queries.append((normalize_query(query), current_db))

    # Pattern 2: Look for queries in JSON results
    json_pattern = r'"sql_query":\s*"(SELECT[^"]+)"'
    json_matches = re.finditer(json_pattern, log_text, re.IGNORECASE)
    for match in json_matches:
        query = match.group(1).strip()
        if query and query != "SELECT NULL -- No query found":
            queries.append((normalize_query(query), current_db))

    # Remove duplicates while preserving order
    seen = set()
    unique_queries = []
    for query, db_id in queries:
        if query not in seen:
            seen.add(query)
            unique_queries.append((query, db_id))

    return unique_queries


def get_final_sql_query(
    results: Dict[str, Any], log_text: str
) -> Optional[Tuple[str, str]]:
    """
    Get the final SQL query and database ID from both results and logs.
    Returns None if no valid queries found.

    Args:
        results: Dictionary containing query results
        log_text: The log text containing SQL queries

    Returns:
        Tuple of (query, database_id) or None if no valid queries found
    """
    # First try to get query from results
    result_queries = extract_sql_queries_from_results(results)
    if result_queries:
        return result_queries[-1]

    # If no queries in results, try logs
    log_queries = extract_sql_queries_from_logs(log_text)
    if log_queries:
        return log_queries[-1]

    return None


def validate_query(query: str, db_id: str) -> bool:
    """
    Validate a SQL query against the schema.

    Args:
        query: SQL query to validate
        db_id: Database ID

    Returns:
        True if query is valid, False otherwise
    """
    if not query or query == "SELECT NULL -- No query found":
        return False

    try:
        # Basic validation of SQL structure
        if not re.match(r"^\s*SELECT\s+", query, re.IGNORECASE):
            logging.error(f"Query does not start with SELECT: {query}")
            return False

        # Check for common SQL injection patterns
        if re.search(
            r";\s*DROP|;\s*DELETE|;\s*UPDATE|;\s*INSERT", query, re.IGNORECASE
        ):
            logging.error(f"Query contains potential SQL injection: {query}")
            return False

        # Check for unmatched quotes
        if query.count("'") % 2 != 0 or query.count('"') % 2 != 0:
            logging.error(f"Query contains unmatched quotes: {query}")
            return False

        # Check for unmatched parentheses
        if query.count("(") != query.count(")"):
            logging.error(f"Query contains unmatched parentheses: {query}")
            return False

        return True

    except Exception as e:
        logging.error(f"Error validating query: {e}")
        return False

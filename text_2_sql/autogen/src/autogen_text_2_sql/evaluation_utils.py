# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import re
from typing import Optional, List, Dict, Any


def extract_sql_queries_from_results(results: Dict[str, Any]) -> List[str]:
    """
    Extract SQL queries from the results dictionary returned by the query processing.

    Args:
        results: Dictionary containing query results

    Returns:
        List of SQL queries found in the results
    """
    queries = []

    if results.get("contains_database_results") and results.get("results"):
        for question_results in results["results"].values():
            for result in question_results:
                if isinstance(result, dict) and "sql_query" in result:
                    sql_query = result["sql_query"].strip()
                    if sql_query and sql_query != "SELECT NULL -- No query found":
                        queries.append(sql_query)

    return queries


def extract_sql_queries_from_logs(log_text: str) -> List[str]:
    """
    Extract SQL queries from the autogen logs.

    Args:
        log_text: The log text containing SQL queries

    Returns:
        List of SQL queries found in the logs
    """
    queries = []

    # Pattern 1: Look for queries after "Running query against"
    running_pattern = r"Running query against.*?: (SELECT.*?)(?=\n|$)"
    running_matches = re.finditer(running_pattern, log_text, re.IGNORECASE)
    for match in running_matches:
        query = match.group(1).strip()
        if query and query != "SELECT NULL -- No query found":
            queries.append(query)

    # Pattern 2: Look for queries in JSON results
    json_pattern = r'"sql_query":\s*"(SELECT[^"]+)"'
    json_matches = re.finditer(json_pattern, log_text, re.IGNORECASE)
    for match in json_matches:
        query = match.group(1).strip()
        if query and query != "SELECT NULL -- No query found":
            queries.append(query)

    # Remove duplicates while preserving order
    seen = set()
    unique_queries = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique_queries.append(query)

    return unique_queries


def get_final_sql_query(results: Dict[str, Any], log_text: str) -> Optional[str]:
    """
    Get the final SQL query from both results and logs.
    Returns None if no valid queries found.

    Args:
        results: Dictionary containing query results
        log_text: The log text containing SQL queries

    Returns:
        The final SQL query or None if no valid queries found
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

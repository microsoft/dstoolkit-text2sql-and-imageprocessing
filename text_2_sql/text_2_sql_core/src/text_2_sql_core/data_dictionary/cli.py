import asyncio
from importlib import metadata
from pathlib import Path
from typing import Annotated
from text_2_sql_core.utils.database import DatabaseEngine

import typer
from rich import print as rich_print

cli = typer.Typer(pretty_exceptions_show_locals=False, no_args_is_help=True)

__version__ = metadata.version(__package__)


def version_callback(value: bool) -> None:
    """Print the version of the CLI."""
    if value:
        print(__version__)
        raise typer.Exit()


@cli.callback()
def callback(
    _: bool = typer.Option(None, "--version", "-v", callback=version_callback)
) -> None:
    """Text2SQL Data Dictionary Creator CLI."""


@cli.command()
def create(
    engine: DatabaseEngine,
    output_directory: Annotated[
        Path | None,
        typer.Option(
            "--output-directory",
            "-o",
            help="Optional directory that the script will write the output files to.",
            show_default=False,
            exists=True,
            file_okay=True,
            dir_okay=False,
            writable=True,
            readable=True,
            resolve_path=True,
        ),
    ] = None,
    single_file: Annotated[
        bool,
        typer.Option(
            "--single_file",
            "-s",
            help="Optional flag that writes all schemas to a single file.",
        ),
    ] = False,
) -> None:
    """Execute a Text2SQL Data Dictionary Creator YAML file.

    Args:
    ----
        engine (DatabaseEngine):

    Returns:
    -------
        None

    """

    try:
        if engine == DatabaseEngine.DATABRICKS:
            from text_2_sql_core.data_dictionary.databricks_data_dictionary_creator import (
                DatabricksDataDictionaryCreator,
            )

            data_dictionary_creator = DatabricksDataDictionaryCreator()
        elif engine == DatabaseEngine.SNOWFLAKE:
            from text_2_sql_core.data_dictionary.snowflake_data_dictionary_creator import (
                SnowflakeDataDictionaryCreator,
            )

            data_dictionary_creator = SnowflakeDataDictionaryCreator()
        elif engine == DatabaseEngine.TSQL:
            from text_2_sql_core.data_dictionary.tsql_data_dictionary_creator import (
                TSQLDataDictionaryCreator,
            )

            data_dictionary_creator = TSQLDataDictionaryCreator()
    except ImportError:
        detailed_error = f"""Failed to import {
            engine.value} Data Dictionary Creator. Check you have installed the optional dependencies for this database engine."""
        rich_print("Text2SQL Data Dictionary Creator Failed ❌")
        rich_print(detailed_error)

        raise typer.Exit(code=1)

    try:
        asyncio.run(data_dictionary_creator.create_data_dictionary())
    except Exception as e:
        rich_print("Text2SQL Data Dictionary Creator Failed ❌")

        rich_print(f"Error Messages: {e}")

        raise typer.Exit(code=1)
    else:
        rich_print("Text2SQL Data Dictionary Creator Completed Successfully ✅")

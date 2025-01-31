import asyncio
from pathlib import Path
from typing import Annotated
from text_2_sql_core.utils.database import DatabaseEngine
import logging
import typer
from rich import print as rich_print
from tenacity import RetryError
import traceback

logging.basicConfig(level=logging.INFO)

cli = typer.Typer(pretty_exceptions_show_locals=False, no_args_is_help=True)


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
    generate_definitions: Annotated[
        bool,
        typer.Option(
            "--generate_definitions",
            "-gen",
            help="Optional flag that will use OpenAI to generate descriptions.",
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

    kwargs = {
        "output_directory": output_directory,
        "single_file": single_file,
        "generate_definitions": generate_definitions,
    }

    try:
        if engine == DatabaseEngine.DATABRICKS:
            from text_2_sql_core.data_dictionary.databricks_data_dictionary_creator import (
                DatabricksDataDictionaryCreator,
            )

            data_dictionary_creator = DatabricksDataDictionaryCreator(
                **kwargs,
            )
        elif engine == DatabaseEngine.SNOWFLAKE:
            from text_2_sql_core.data_dictionary.snowflake_data_dictionary_creator import (
                SnowflakeDataDictionaryCreator,
            )

            data_dictionary_creator = SnowflakeDataDictionaryCreator(
                **kwargs,
            )
        elif engine == DatabaseEngine.TSQL:
            from text_2_sql_core.data_dictionary.tsql_data_dictionary_creator import (
                TsqlDataDictionaryCreator,
            )

            data_dictionary_creator = TsqlDataDictionaryCreator(
                **kwargs,
            )
        elif engine == DatabaseEngine.POSTGRES:
            from text_2_sql_core.data_dictionary.postgres_data_dictionary_creator import (
                PostgresDataDictionaryCreator,
            )

            data_dictionary_creator = PostgresDataDictionaryCreator(
                **kwargs,
            )
        else:
            rich_print("Text2SQL Data Dictionary Creator Failed ❌")
            rich_print(f"Database Engine {engine.value} is not supported.")

            raise typer.Exit(code=1)
    except Exception as e:
        logging.error(e)
        detailed_error = f"""Failed to import {
            engine.value} Data Dictionary Creator. Check you have installed the optional dependencies for this database engine and have configured all the environmental variables."""
        rich_print("Text2SQL Data Dictionary Creator Failed ❌")
        rich_print(detailed_error)
        rich_print(f"Error Messages: {traceback.format_exc()}")

        raise typer.Exit(code=1)

    try:
        asyncio.run(data_dictionary_creator.create_data_dictionary())
    except RetryError as e:
        # Fetch the actual exception
        e = e.last_attempt.exception()
        logging.error(e)
        rich_print("Text2SQL Data Dictionary Creator Failed ❌")

        rich_print(f"Error Messages: {e}")
        rich_print(traceback.format_exc())

        raise typer.Exit(code=1)
    except Exception as e:
        logging.error(e)

        rich_print("Text2SQL Data Dictionary Creator Failed ❌")

        rich_print(f"Error Messages: {traceback.format_exc()}")

        raise typer.Exit(code=1)
    else:
        rich_print("Text2SQL Data Dictionary Creator Completed Successfully ✅")


if __name__ == "__main__":
    cli()

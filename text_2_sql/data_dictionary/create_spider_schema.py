from text_2_sql_core.data_dictionary.sqlite_data_dictionary_creator import (
    SQLiteDataDictionaryCreator,
)
from text_2_sql_core.data_dictionary.data_dictionary_creator import (
    EntityItem,
    ColumnItem,
)
from dotenv import load_dotenv
import json
import sqlite3
import aiosqlite
from pathlib import Path
import asyncio
import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)


# Load environment variables from autogen .env file
autogen_env_path = Path(__file__).parent.parent / "autogen" / ".env"
load_dotenv(autogen_env_path)

# Configure OpenAI settings
os.environ[
    "OpenAI__CompletionDeployment"
] = "gpt-4o-mini"  # Use mini model for faster processing
os.environ[
    "OpenAI__MiniCompletionDeployment"
] = "gpt-4o-mini"  # Use mini model for both
os.environ["OPENAI_API_TYPE"] = "azure"
os.environ["OPENAI_API_VERSION"] = os.getenv("OpenAI__ApiVersion")
os.environ["OPENAI_API_BASE"] = os.getenv("OpenAI__Endpoint")
os.environ["OPENAI_API_KEY"] = os.getenv("OpenAI__ApiKey")

# SQLite system tables that should be skipped
SQLITE_SYSTEM_TABLES = {
    "sqlite_sequence",
    "sqlite_stat1",
    "sqlite_stat2",
    "sqlite_stat3",
    "sqlite_stat4",
}


def get_processed_entities(schema_store_dir: Path) -> set:
    """Get list of entities that have already been processed."""
    processed = set()
    if schema_store_dir.exists():
        for f in schema_store_dir.glob("*.json"):
            # Extract entity name from filename (e.g., spider_schema.db.main.PROFESSOR.json -> PROFESSOR)
            parts = f.stem.split(".")
            if len(parts) >= 4:  # Ensure we have enough parts (db.schema.table)
                entity = parts[-1]  # Get the last part which is the table name
                # Store in uppercase for consistent comparison
                processed.add(entity.upper())
                logger.info(f"Found processed schema for entity: {entity}")
    return processed


def merge_sqlite_databases(source_dir: Path, target_db: Path) -> None:
    """Merge all SQLite databases from source directory into target database."""
    # Only create database if it doesn't exist
    if target_db.exists():
        logger.info(f"\nUsing existing SQLite database at: {target_db}")
        return

    logger.info(f"\nCreating new SQLite database at: {target_db}")
    target_db.parent.mkdir(parents=True, exist_ok=True)

    # Create target database
    with sqlite3.connect(target_db) as target_conn:
        target_cursor = target_conn.cursor()

        # Process each source database
        for db_dir in source_dir.iterdir():
            if not db_dir.is_dir():
                continue

            db_file = db_dir / f"{db_dir.name}.sqlite"
            if not db_file.exists():
                continue

            logger.info(f"\nProcessing database: {db_dir.name}")

            try:
                # Attach source database
                target_cursor.execute("ATTACH DATABASE ? AS source", (str(db_file),))

                # Get list of tables from source database
                target_cursor.execute(
                    """
                    SELECT name FROM source.sqlite_master
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """
                )
                tables = target_cursor.fetchall()

                # Copy each table
                for (table_name,) in tables:
                    logger.info(f"Copying table: {table_name}")

                    # Create table in target database
                    target_cursor.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS "{table_name}" AS
                        SELECT * FROM source."{table_name}"
                    """
                    )

                    # Copy indexes
                    target_cursor.execute(
                        """
                        SELECT sql FROM source.sqlite_master
                        WHERE type='index' AND tbl_name=? AND sql IS NOT NULL
                    """,
                        (table_name,),
                    )
                    indexes = target_cursor.fetchall()
                    for (index_sql,) in indexes:
                        try:
                            target_cursor.execute(index_sql)
                        except sqlite3.OperationalError:
                            # Skip if index already exists
                            pass

                # Detach source database
                target_cursor.execute("DETACH DATABASE source")

            except sqlite3.Error as e:
                logger.error(f"Error processing {db_dir.name}: {e}")
                continue

        target_conn.commit()


class ProgressTrackingDataDictionaryCreator(SQLiteDataDictionaryCreator):
    """Extension of SQLiteDataDictionaryCreator that tracks progress and limits relationship depth."""

    def __init__(self, processed_entities: set, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processed_entities = processed_entities
        logger.info(f"Initialized with output directory: {self.output_directory}")

    def extract_distinct_values_sql_query(
        self, entity: EntityItem, column: ColumnItem
    ) -> str:
        """Override to handle SQLite column names."""
        return f"""
        SELECT DISTINCT "{column.name}"
        FROM "{entity.entity}"
        WHERE "{column.name}" IS NOT NULL
        ORDER BY "{column.name}" DESC
        LIMIT 1000;
        """

    async def send_request_to_llm(
        self,
        system_prompt: str,
        input: str,
        max_retries: int = 3,
        retry_delay: int = 60,
    ):
        """Override to handle rate limits better."""
        for attempt in range(max_retries):
            try:
                messages = [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": input,
                            },
                        ],
                    },
                ]

                # Use mini model for faster processing
                return await self.open_ai_connector.run_completion_request(
                    messages, model="gpt-4o-mini"
                )
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    logger.info(f"Hit rate limit, waiting {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    continue
                raise e

    async def extract_column_distinct_values(
        self, entity: EntityItem, column: ColumnItem
    ):
        """Override to extract and write column values with correct format."""
        try:
            logger.info(f"Extracting values for {entity.entity}.{column.name}")

            # Query to get sample values first
            sample_query = f"""
            SELECT DISTINCT "{column.name}"
            FROM "{entity.entity}"
            WHERE "{column.name}" IS NOT NULL
            ORDER BY RANDOM()
            LIMIT 5;
            """

            sample_values = await self.query_entities(sample_query)

            # Convert sample values to proper format
            column.sample_values = []
            for value in sample_values:
                if value[0] is not None:
                    # Remove any whitespace characters for string values
                    if isinstance(value[0], str):
                        column.sample_values.append(
                            re.sub(r"[\t\n\r\f\v]+", "", value[0])
                        )
                    else:
                        column.sample_values.append(value[0])

            # For string columns, also get all distinct values for column value store
            if any(
                data_type in column.data_type.lower()
                for data_type in ["string", "nchar", "text", "varchar"]
            ):
                logger.info(f"Writing values for {entity.entity}.{column.name}")

                # Get all distinct values
                distinct_query = f"""
                SELECT DISTINCT "{column.name}"
                FROM "{entity.entity}"
                WHERE "{column.name}" IS NOT NULL
                ORDER BY "{column.name}" DESC
                LIMIT 1000;
                """

                distinct_values = await self.query_entities(distinct_query)

                # Create column value store directory
                column_store_dir = os.path.join(
                    self.output_directory, "column_value_store"
                )
                os.makedirs(column_store_dir, exist_ok=True)

                # Write column values with correct format
                column_file = os.path.join(
                    column_store_dir, f"{entity.entity}.{column.name}.jsonl"
                )
                logger.info(f"Writing to: {column_file}")
                with open(column_file, "w", encoding="utf-8") as f:
                    for value in distinct_values:
                        if value[0] is not None:
                            # Clean the value
                            clean_value = re.sub(r"[\t\n\r\f\v]+", "", str(value[0]))
                            json.dump(
                                {
                                    "Entity": entity.entity,
                                    "Schema": entity.entity_schema or "main",
                                    "Database": "spider_schema",
                                    "FQN": f"spider_schema.{entity.entity_schema or 'main'}.{entity.entity}.{column.name}",
                                    "Column": column.name,
                                    "Value": clean_value,
                                    "Synonyms": [],
                                },
                                f,
                            )
                            f.write("\n")

        except Exception as e:
            logger.error(f"Error processing {entity.entity}.{column.name}: {e}")
            raise

    async def generate_entity_definition(self, entity: EntityItem):
        """Generate a brief name and definition for an entity."""
        try:
            # Generate a shorter name prompt
            name_system_prompt = """Generate a brief, human-readable name for this SQL Entity (e.g. 'Sales Data', 'Customer Info', 'Products')."""
            name_input = f"Name for table: {entity.entity}"

            # Generate a shorter definition prompt
            definition_system_prompt = """Generate a brief definition (2-3 sentences) for this SQL Entity. Include what data it contains and what questions it can answer."""
            definition_input = f"Define table {entity.entity} with columns: {', '.join([column.name for column in entity.columns])}"

            # Add existing definition if available
            if entity.definition is not None:
                name_input += f"\nExisting definition: {entity.definition}"
                definition_input += f"\nExisting definition: {entity.definition}"

            # Get name with retries
            name = await self.send_request_to_llm(name_system_prompt, name_input)
            logger.info(f"Generated name for {entity.entity}: {name}")
            entity.entity_name = name

            # Wait briefly between name and definition
            await asyncio.sleep(5)

            # Get definition with retries
            definition = await self.send_request_to_llm(
                definition_system_prompt, definition_input
            )
            logger.info(f"Generated definition for {entity.entity}: {definition}")
            entity.definition = definition

            # Generate column definitions
            for column in entity.columns:
                column_def_prompt = f"""Generate a brief description for the column '{column.name}' of type {column.data_type} in the {entity.entity} table."""
                column.definition = await self.send_request_to_llm(
                    "Generate a brief column description.", column_def_prompt
                )

        except Exception as e:
            logger.error(f"Error generating definitions for {entity.entity}: {e}")
            raise e

    def apply_exclusions_to_entity(self, entity: EntityItem) -> dict:
        """Override to produce schema output matching the example format exactly."""
        logger.info(f"Applying exclusions for entity: {entity.entity}")

        # Format matching the schema store example order exactly
        simplified_data = {
            "Columns": [
                {
                    "DataType": col.data_type,
                    "Definition": col.definition,
                    "Name": col.name,
                    "SampleValues": col.sample_values
                    if hasattr(col, "sample_values")
                    else [],
                }
                for col in entity.columns
            ],
            "CompleteEntityRelationshipsGraph": entity.complete_entity_relationships_graph
            if hasattr(entity, "complete_entity_relationships_graph")
            else [],
            "Database": "spider_schema",
            "Definition": entity.definition,
            "Entity": entity.entity,
            "EntityName": entity.entity_name,
            "EntityRelationships": [
                {
                    "FQN": f"spider_schema.main.{entity.entity}",
                    "ForeignDatabase": "spider_schema",
                    "ForeignEntity": rel.foreign_entity,
                    "ForeignSchema": "main",
                    "ForeignFQN": f"spider_schema.main.{rel.foreign_entity}",
                    "ForeignKeys": [
                        {"Column": fk.column, "ForeignColumn": fk.foreign_column}
                        for fk in rel.foreign_keys
                    ],
                }
                for rel in entity.entity_relationships
            ]
            if hasattr(entity, "entity_relationships") and entity.entity_relationships
            else [],
            "FQN": f"spider_schema.{entity.entity_schema or 'main'}.{entity.entity}",
            "Schema": entity.entity_schema or "main",
        }

        return simplified_data

    async def build_entity_entry(self, entity: EntityItem) -> EntityItem:
        """Override to handle both schema and column value progress."""
        entity_upper = entity.entity.upper()

        # Always get the columns first
        logger.info(f"Getting columns for entity: {entity.entity}")
        columns = await self.query_entities(
            self.extract_columns_sql_query(entity), cast_to=ColumnItem
        )
        entity.columns = columns
        logger.info(f"Found {len(columns)} columns")

        # Process column values first to ensure sample values are available
        logger.info(f"Processing column values for entity: {entity.entity}")
        for column in entity.columns:
            logger.info(f"Processing column: {column.name}")
            await self.extract_column_distinct_values(entity, column)

        # If we've already processed the schema, load it from file
        if entity_upper in self.processed_entities:
            logger.info(f"Skipping schema generation for entity: {entity.entity}")
            schema_store_dir = os.path.join(self.output_directory, "schema_store")
            schema_file = os.path.join(
                schema_store_dir, f"spider_schema.db.main.{entity.entity}.json"
            )
            if os.path.exists(schema_file):
                with open(schema_file) as f:
                    schema_data = json.load(f)
                    entity.definition = schema_data.get("Definition")
                    entity.entity_name = schema_data.get("EntityName")
        else:
            logger.info(f"Generating schema for entity: {entity.entity}")
            await self.generate_entity_definition(entity)

            # Get relationships
            try:
                # Query to get only direct foreign key relationships
                query = """
                SELECT
                    m.name as main_table,
                    p."from" as from_column,
                    p."to" as to_column,
                    p.`table` as referenced_table
                FROM sqlite_master m
                JOIN pragma_foreign_key_list(m.name) p
                WHERE m.name = ?
                """

                relationships = []
                direct_relationships = []

                async with aiosqlite.connect(self.database_path) as db:
                    async with db.execute(query, (entity.entity,)) as cursor:
                        async for row in cursor:
                            relationship = {
                                "foreign_entity": row[3],
                                "foreign_entity_schema": "main",
                                "foreign_keys": [
                                    {"column": row[1], "foreign_column": row[2]}
                                ],
                            }
                            relationships.append(relationship)
                            # Only store direct relationships in the graph
                            direct_relationships.append(
                                f"spider_schema.main.{entity.entity} -> {row[3]}"
                            )

                entity.entity_relationships = relationships
                entity.complete_entity_relationships_graph = direct_relationships
            except Exception as e:
                logger.error(
                    f"Error getting relationships for {entity.entity}: {str(e)}"
                )
                entity.entity_relationships = []
                entity.complete_entity_relationships_graph = []

            # Write schema file
            schema_store_dir = os.path.join(self.output_directory, "schema_store")
            os.makedirs(schema_store_dir, exist_ok=True)
            schema_file = os.path.join(
                schema_store_dir, f"spider_schema.db.main.{entity.entity}.json"
            )
            logger.info(f"Writing schema to: {schema_file}")
            with open(schema_file, "w", encoding="utf-8") as f:
                json.dump(
                    self.apply_exclusions_to_entity(entity),
                    f,
                    indent=4,
                    default=str,
                )

        return entity


async def main():
    # Get paths
    current_dir = Path(__file__).parent
    spider_data_dir = current_dir.parent / "spider_data"
    database_dir = spider_data_dir / "database"

    if not database_dir.exists():
        raise FileNotFoundError(f"Database directory not found at {database_dir}")

    # Create output directories with simplified structure
    output_dir = current_dir / "generated_samples"
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created output directory: {output_dir}")

    # Create SQLite database by merging all source databases
    db_path = output_dir / "spider_schema.db"
    merge_sqlite_databases(database_dir, db_path)

    # Get list of already processed entities
    schema_store_dir = output_dir / "schema_store"
    processed_entities = get_processed_entities(schema_store_dir)
    logger.info(f"\nFound {len(processed_entities)} processed schemas")

    # Generate enhanced data dictionary
    creator = ProgressTrackingDataDictionaryCreator(
        processed_entities=processed_entities,
        # Use absolute path to avoid directory change issues
        database_path=str(db_path.absolute()),
        # DataDictionaryCreator will append schema_store
        output_directory=str(output_dir),
        generate_definitions=True,
        excluded_schemas=[],  # Empty list since SQLite doesn't use schemas like SQL Server
        single_file=False,  # Generate individual files for AI Search indexing
    )

    try:
        # Get all entities first
        entities = await creator.extract_entities_with_definitions()
        total_entities = len(entities)
        logger.info(f"\nFound {total_entities} total entities")

        # Process in smaller batches
        batch_size = 3  # Process 3 entities at a time
        for i in range(0, total_entities, batch_size):
            batch = entities[i : i + batch_size]
            logger.info(
                f"\nProcessing batch {i//batch_size + 1} ({len(batch)} entities)"
            )

            # Process each entity in the batch
            for entity in batch:
                try:
                    logger.info(f"Processing entity: {entity.entity}")
                    await creator.build_entity_entry(entity)
                    logger.info(f"Successfully processed {entity.entity}")
                except Exception as e:
                    logger.error(f"Error processing entity {entity.entity}: {e}")
                    if "429" in str(e):
                        logger.info("Hit rate limit, waiting 60 seconds...")
                        await asyncio.sleep(60)  # Wait longer when hitting rate limit
                        # Try this entity again
                        try:
                            logger.info(f"Retrying entity: {entity.entity}")
                            await creator.build_entity_entry(entity)
                            logger.info(
                                f"Successfully processed {entity.entity} on retry"
                            )
                        except Exception as retry_e:
                            logger.error(
                                f"Failed to process {entity.entity} on retry: {retry_e}"
                            )
                            if "429" in str(retry_e):
                                logger.info(
                                    "Still hitting rate limit, saving progress..."
                                )
                                break
                            else:
                                raise retry_e
                    else:
                        raise e

            logger.info(f"Completed batch {i//batch_size + 1}")

        logger.info("\nGenerated data dictionary files in:")
        logger.info(f"- Schema definitions: {output_dir}/schema_store")
        logger.info(f"- Column values: {output_dir}/column_value_store")
        print("\nNext steps:")
        print("1. Wait for rate limits to reset if needed")
        print("2. Run the script again to continue processing remaining entities")
        print(
            "3. Once all entities are processed, deploy to AI Search using deploy_ai_search"
        )
        print("4. Update the environment settings to use AI Search indices")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise e


if __name__ == "__main__":
    asyncio.run(main())

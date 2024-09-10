# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from common.ai_search import AISearchHelper, IndexerStatusEnum
from common.service_bus import ServiceBusHelper
from common.payloads.pending_index_trigger import PendingIndexTriggerPayload
from common.payloads.pending_index_completion import PendingIndexCompletionPayload
from common.payloads.header import TaskEnum
from datetime import datetime, timedelta, timezone
from common.delay_processing_exception import DelayProcessingException
from common.payloads.error import Error


async def process_pending_index_trigger(payload: PendingIndexTriggerPayload):
    """Process the pending index trigger."""

    ai_search_helper = AISearchHelper()
    service_bus_helper = ServiceBusHelper()

    status, indexer_start_time = await ai_search_helper.get_indexer_status(
        payload.body.indexer
    )
    request_time = payload.header.last_processed_timestamp
    enqueue_time = None
    queue = None
    message = None
    retry = False

    if status == IndexerStatusEnum.SUCCESS and indexer_start_time > request_time:
        errors = [error_item.model_dump() for error_item in payload.errors]
        message = PendingIndexCompletionPayload(
            header=payload.header.model_dump(),
            body=payload.body.model_dump(),
            errors=errors,
        )
        queue = TaskEnum.PENDING_INDEX_COMPLETION
    elif status == IndexerStatusEnum.RETRIGGER or status == IndexerStatusEnum.SUCCESS:
        # Trigger the indexer
        await ai_search_helper.trigger_indexer(payload.body.indexer)

        errors = [error_item.model_dump() for error_item in payload.errors]

        if status == IndexerStatusEnum.RETRIGGER:
            errors.append(
                Error(
                    code="IndexerNotCompleted",
                    message="Indexer was was in failed state and required retriggering.",
                )
            )

        message = PendingIndexCompletionPayload(
            header=payload.header.model_dump(),
            body=payload.body.model_dump(),
            errors=errors,
        )
        queue = TaskEnum.PENDING_INDEX_COMPLETION
    elif status == IndexerStatusEnum.RUNNING and indexer_start_time > request_time:
        errors = [error_item.model_dump() for error_item in payload.errors]
        message = PendingIndexCompletionPayload(
            header=payload.header.model_dump(),
            body=payload.body.model_dump(),
            errors=errors,
        )
        queue = TaskEnum.PENDING_INDEX_COMPLETION
    elif (
        status == IndexerStatusEnum.RUNNING
        and indexer_start_time <= request_time
        and payload.header.retries_remaining > 0
    ):
        errors = [error_item.model_dump() for error_item in payload.errors]
        errors.append(
            Error(
                code="IndexerAlreadyRunning",
                message="Indexer is already running for an outstanding request.",
            )
        )
        message = PendingIndexTriggerPayload(
            header=payload.header.model_dump(),
            body=payload.body.model_dump(),
            errors=errors,
        )
        queue = TaskEnum.PENDING_INDEX_TRIGGER
        minutes = 2 ** (11 - payload.header.retries_remaining)
        enqueue_time = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        retry = True
    else:
        raise DelayProcessingException(
            "Failed to run trigger due to maximum retries exceeded."
        )

    if queue is not None:
        await service_bus_helper.send_message_to_service_bus_queue(
            queue, message, enqueue_time=enqueue_time, retry=retry
        )

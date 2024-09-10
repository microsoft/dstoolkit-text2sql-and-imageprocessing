# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import logging
from datetime import datetime, timezone
from azure.identity.aio import DefaultAzureCredential
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient


class ServiceBusHelper:
    def __init__(self):
        self._client_id = os.environ["FunctionApp__ClientId"]

        self._endpoint = os.environ["ServiceBusTrigger__fullyQualifiedNamespace"]

    async def get_client(self):
        credential = DefaultAzureCredential(managed_identity_client_id=self._client_id)
        return ServiceBusClient(self._endpoint, credential)

    async def send_message_to_service_bus_queue(
        self, queue, payload, enqueue_time=None, retry=False
    ):
        # update the header
        payload.header.last_processed_timestamp = datetime.now(timezone.utc)
        payload.header.task = queue

        if retry:
            payload.header.retries_remaining -= 1
        try:
            service_bus_client = await self.get_client()
            async with service_bus_client:
                sender = service_bus_client.get_queue_sender(queue_name=queue.value)

                async with sender:
                    message = ServiceBusMessage(
                        body=payload.model_dump_json(),
                        scheduled_enqueue_time_utc=enqueue_time,
                    )
                    await sender.send_messages(message)
                    logging.info(
                        f"Sent a message to the Azure Service Bus queue: {queue}"
                    )
        except Exception as e:
            logging.error(f"Failed to send message to the Azure Service Bus queue: {e}")

from pydantic import BaseModel, ConfigDict
import logging


class Payload(BaseModel):
    """Body model"""

    @classmethod
    def from_service_bus_message(cls, message):
        """
        Create a Payload object from a ServiceBusMessage object.

        :param message: The ServiceBusMessage object.
        :return: The Body object.
        """
        message = message.get_body().decode("utf-8")
        logging.info(f"ServiceBus message: {message}")
        return cls.model_validate_json(message)

    __config__ = ConfigDict(extra="ignore")

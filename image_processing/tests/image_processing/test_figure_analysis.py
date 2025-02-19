# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pytest
import base64
import io
from PIL import Image
from unittest.mock import AsyncMock, MagicMock
from tenacity import RetryError
from openai import OpenAIError, RateLimitError
from figure_analysis import FigureAnalysis
from layout_holders import FigureHolder
from httpx import Response, Request

# ------------------------
# Fixtures for Image Data
# ------------------------


@pytest.fixture
def image_data_100x100():
    """Return a base64-encoded PNG image of size 100x100."""
    img = Image.new("RGB", (100, 100), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    data = buffer.getvalue()
    return base64.b64encode(data).decode("utf-8")


@pytest.fixture
def image_data_50x50():
    """Return a base64-encoded PNG image of size 50x50 (small image)."""
    img = Image.new("RGB", (50, 50), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    data = buffer.getvalue()
    return base64.b64encode(data).decode("utf-8")


# ------------------------
# Fixtures for FigureHolder
# ------------------------


@pytest.fixture
def valid_figure(image_data_100x100):
    """
    A valid figure with sufficient size.
    Example: FigureHolder(figure_id='12345', description="Figure 1", uri="https://example.com/12345.png", offset=50, length=17)
    """
    return FigureHolder(
        figure_id="12345",
        description="Figure 1",
        uri="https://example.com/12345.png",
        offset=50,
        length=17,
        data=image_data_100x100,
    )


@pytest.fixture
def small_figure(image_data_50x50):
    """A figure whose image is too small (both dimensions below 75)."""
    return FigureHolder(
        figure_id="small1",
        description="",
        uri="https://example.com/small1.png",
        offset=0,
        length=10,
        data=image_data_50x50,
    )


# ------------------------
# Tests for get_image_size
# ------------------------


def test_get_image_size(valid_figure):
    analysis = FigureAnalysis()
    width, height = analysis.get_image_size(valid_figure)
    assert width == 100
    assert height == 100


def test_get_image_size_small(small_figure):
    analysis = FigureAnalysis()
    width, height = analysis.get_image_size(small_figure)
    assert width == 50
    assert height == 50


# ------------------------
# Tests for understand_image_with_gptv
# ------------------------


@pytest.mark.asyncio
async def test_understand_image_with_gptv_small(small_figure):
    """
    If both width and height are below 75, the image should be considered too small,
    and its description set to "Irrelevant Image".
    """
    analysis = FigureAnalysis()
    updated_figure = await analysis.understand_image_with_gptv(small_figure)
    assert updated_figure.description == "Irrelevant Image"


@pytest.mark.asyncio
async def test_understand_image_with_gptv_success(valid_figure, monkeypatch):
    """
    Test the success branch of understand_image_with_gptv.
    Patch AsyncAzureOpenAI to simulate a successful response.
    """
    analysis = FigureAnalysis()

    # Set up required environment variables.
    monkeypatch.setenv("OpenAI__ApiVersion", "2023-07-01-preview")
    monkeypatch.setenv("OpenAI__MiniCompletionDeployment", "deployment123")
    monkeypatch.setenv("OpenAI__Endpoint", "https://example.openai.azure.com")

    # Create a dummy response object to mimic the client's response.
    dummy_response = MagicMock()
    dummy_choice = MagicMock()
    dummy_message = MagicMock()
    dummy_message.content = "Generated image description"
    dummy_choice.message = dummy_message
    dummy_response.choices = [dummy_choice]

    # Create a dummy async client whose chat.completions.create returns dummy_response.
    dummy_client = AsyncMock()
    dummy_client.chat.completions.create.return_value = dummy_response

    # Create a dummy async context manager that returns dummy_client.
    dummy_async_context = AsyncMock()
    dummy_async_context.__aenter__.return_value = dummy_client

    # Patch AsyncAzureOpenAI so that instantiating it returns our dummy context manager.
    monkeypatch.setattr(
        "figure_analysis.AsyncAzureOpenAI", lambda **kwargs: dummy_async_context
    )

    # Call the function and verify the description is set from the dummy response.
    updated_figure = await analysis.understand_image_with_gptv(valid_figure)
    assert updated_figure.description == "Generated image description"

    # Now simulate the case when the API returns an empty description.
    dummy_message.content = ""
    updated_figure = await analysis.understand_image_with_gptv(valid_figure)
    assert updated_figure.description == "Irrelevant Image"


@pytest.mark.asyncio
async def test_understand_image_with_gptv_policy_violation(valid_figure, monkeypatch):
    """
    If the OpenAI API raises an error with "ResponsibleAIPolicyViolation" in its message,
    the description should be set to "Irrelevant Image".
    """
    analysis = FigureAnalysis()
    monkeypatch.setenv("OpenAI__ApiVersion", "2023-07-01-preview")
    monkeypatch.setenv("OpenAI__MiniCompletionDeployment", "deployment123")
    monkeypatch.setenv("OpenAI__Endpoint", "https://example.openai.azure.com")

    # Define a dummy exception that mimics an OpenAI error with a ResponsibleAIPolicyViolation message.
    class DummyOpenAIError(OpenAIError):
        def __init__(self, message):
            self.message = message

    async def dummy_create(*args, **kwargs):
        raise DummyOpenAIError("Error: ResponsibleAIPolicyViolation occurred")

    dummy_client = AsyncMock()
    dummy_client.chat.completions.create.side_effect = dummy_create
    dummy_async_context = AsyncMock()
    dummy_async_context.__aenter__.return_value = dummy_client
    monkeypatch.setattr(
        "figure_analysis.AsyncAzureOpenAI", lambda **kwargs: dummy_async_context
    )

    updated_figure = await analysis.understand_image_with_gptv(valid_figure)
    assert updated_figure.description == "Irrelevant Image"


@pytest.mark.asyncio
async def test_understand_image_with_gptv_general_error(valid_figure, monkeypatch):
    """
    If the OpenAI API raises an error that does not include "ResponsibleAIPolicyViolation",
    the error should propagate.
    """
    analysis = FigureAnalysis()
    monkeypatch.setenv("OpenAI__ApiVersion", "2023-07-01-preview")
    monkeypatch.setenv("OpenAI__MiniCompletionDeployment", "deployment123")
    monkeypatch.setenv("OpenAI__Endpoint", "https://example.openai.azure.com")

    class DummyOpenAIError(OpenAIError):
        def __init__(self, message):
            self.message = message

    async def dummy_create(*args, **kwargs):
        raise DummyOpenAIError("Some other error")

    dummy_client = AsyncMock()
    dummy_client.chat.completions.create.side_effect = dummy_create
    dummy_async_context = AsyncMock()
    dummy_async_context.__aenter__.return_value = dummy_client
    monkeypatch.setattr(
        "figure_analysis.AsyncAzureOpenAI", lambda **kwargs: dummy_async_context
    )

    with pytest.raises(RetryError) as e:
        await analysis.understand_image_with_gptv(valid_figure)

        root_cause = e.last_attempt.exception()
        assert isinstance(root_cause, DummyOpenAIError)


# ------------------------
# Tests for analyse
# ------------------------


@pytest.mark.asyncio
async def test_analyse_success(valid_figure, monkeypatch):
    """
    Test the successful execution of the analyse method.
    Patch understand_image_with_gptv to return a figure with an updated description.
    """
    analysis = FigureAnalysis()
    record = {"recordId": "rec1", "data": {"figure": valid_figure.model_dump()}}

    async def dummy_understand(figure):
        figure.description = "Updated Description"
        return figure

    monkeypatch.setattr(analysis, "understand_image_with_gptv", dummy_understand)
    result = await analysis.analyse(record)
    assert result["recordId"] == "rec1"
    assert result["data"]["updated_figure"]["description"] == "Updated Description"
    assert result["errors"] is None


@pytest.mark.asyncio
async def test_analyse_retry_rate_limit(valid_figure, monkeypatch):
    """
    Simulate a RetryError whose last attempt raised a RateLimitError.
    The analyse method should return an error message indicating a rate limit error.
    """
    analysis = FigureAnalysis()
    record = {"recordId": "rec2", "data": {"figure": valid_figure.model_dump()}}

    # Create a mock request object
    dummy_request = Request(
        method="POST", url="https://api.openai.com/v1/chat/completions"
    )

    # Create a mock response object with the request set
    dummy_response = Response(
        status_code=429, content=b"Rate limit exceeded", request=dummy_request
    )

    # Create a RateLimitError instance
    dummy_rate_error = RateLimitError(
        message="Rate limit exceeded",
        response=dummy_response,
        body="Rate limit exceeded",
    )
    dummy_retry_error = RetryError(
        last_attempt=MagicMock(exception=lambda: dummy_rate_error)
    )

    async def dummy_understand(figure):
        raise dummy_retry_error

    monkeypatch.setattr(analysis, "understand_image_with_gptv", dummy_understand)
    result = await analysis.analyse(record)
    assert result["recordId"] == "rec2"
    assert result["data"] is None
    assert result["errors"] is not None
    assert "rate limit error" in result["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_analyse_general_exception(valid_figure, monkeypatch):
    """
    If understand_image_with_gptv raises a general Exception,
    analyse should catch it and return an error response.
    """
    analysis = FigureAnalysis()
    record = {"recordId": "rec3", "data": {"figure": valid_figure.model_dump()}}

    async def dummy_understand(figure):
        raise Exception("General error")

    monkeypatch.setattr(analysis, "understand_image_with_gptv", dummy_understand)
    result = await analysis.analyse(record)
    assert result["recordId"] == "rec3"
    assert result["data"] is None
    assert result["errors"] is not None
    assert "check the logs for more details" in result["errors"][0]["message"].lower()

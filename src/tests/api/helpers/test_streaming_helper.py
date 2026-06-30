import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from helpers.streaming_helper import stream_processor


@pytest.mark.asyncio
async def test_stream_processor_yields_content():
    # Mock message with content
    message1 = MagicMock()
    message1.content = "message 1"
    message2 = MagicMock()
    message2.content = "message 2"

    # Mock async generator
    response = AsyncMock()
    response.__aiter__.return_value = [message1, message2]

    # Collect results
    result = [msg async for msg in stream_processor(response)]

    assert result == ["message 1", "message 2"]


@pytest.mark.asyncio
async def test_stream_processor_skips_empty_content():
    # Mock message with empty content
    message1 = MagicMock()
    message1.content = ""
    message2 = MagicMock()
    message2.content = "message 2"

    response = AsyncMock()
    response.__aiter__.return_value = [message1, message2]

    result = [msg async for msg in stream_processor(response)]

    assert result == ["message 2"]


@pytest.mark.asyncio
async def test_stream_processor_logs_and_raises_on_exception():
    response = AsyncMock()
    
    # Simulate error during iteration
    async def mock_iter():
        raise RuntimeError("stream error")
        yield  # This is unreachable, but needed to define async generator

    response.__aiter__.side_effect = mock_iter

    with patch("helpers.streaming_helper.logging.error") as mock_log:
        with pytest.raises(RuntimeError, match="stream error"):
            async for _ in stream_processor(response):
                pass

        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        assert "Error processing streaming response" in args[0]
        assert kwargs["exc_info"] is True

import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock

import helpers.utils as utils


@pytest.mark.asyncio
async def test_format_as_ndjson_success():
    mock_data = [{"key": "value"}, {"another": "entry"}]

    async def async_gen():
        for item in mock_data:
            yield item

    result = []
    async for line in utils.format_as_ndjson(async_gen()):
        result.append(line.strip())

    expected = [json.dumps(item) for item in mock_data]
    assert result == expected


@pytest.mark.asyncio
async def test_format_as_ndjson_exception():
    async def async_gen():
        raise Exception("Test error")
        yield

    result = []
    async for line in utils.format_as_ndjson(async_gen()):
        result.append(json.loads(line.strip()))
    assert result[0]["error"] == "Test error"


def test_parse_multi_columns_pipe():
    assert utils.parse_multi_columns("a|b|c") == ["a", "b", "c"]


def test_parse_multi_columns_comma():
    assert utils.parse_multi_columns("a,b,c") == ["a", "b", "c"]


@patch("helpers.utils.requests.get")
def test_fetchUserGroups_success(mock_get):
    mock_response = {
        "value": [{"id": "123"}],
    }
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = mock_response

    result = utils.fetchUserGroups("fake_token")
    assert result == [{"id": "123"}]


@patch("helpers.utils.requests.get")
def test_fetchUserGroups_with_nextLink(mock_get):
    mock_response_1 = {
        "value": [{"id": "123"}],
        "@odata.nextLink": "next_link"
    }
    mock_response_2 = {
        "value": [{"id": "456"}],
    }

    def side_effect(url, headers):
        mock = MagicMock()
        if url == "https://graph.microsoft.com/v1.0/me/transitiveMemberOf?$select=id":
            mock.status_code = 200
            mock.json.return_value = mock_response_1
        else:
            mock.status_code = 200
            mock.json.return_value = mock_response_2
        return mock

    mock_get.side_effect = side_effect

    result = utils.fetchUserGroups("fake_token")
    assert {"id": "123"} in result and {"id": "456"} in result


@patch("helpers.utils.requests.get", side_effect=Exception("Request error"))
def test_fetchUserGroups_exception(mock_get):
    result = utils.fetchUserGroups("fake_token")
    assert result == []


@patch("helpers.utils.fetchUserGroups")
@patch("helpers.utils.AZURE_SEARCH_PERMITTED_GROUPS_COLUMN", "group_column")
def test_generateFilterString(mock_fetch):
    mock_fetch.return_value = [{"id": "1"}, {"id": "2"}]
    result = utils.generateFilterString("token")
    assert "group_column/any(g:search.in(g, '1, 2'))" in result


@patch("helpers.utils.fetchUserGroups", return_value=[])
@patch("helpers.utils.AZURE_SEARCH_PERMITTED_GROUPS_COLUMN", "group_column")
def test_generateFilterString_empty_groups(mock_fetch):
    result = utils.generateFilterString("token")
    assert "group_column/any(g:search.in(g, ''))" in result


def test_format_non_streaming_response_with_context():
    chatCompletion = MagicMock()
    chatCompletion.id = "1"
    chatCompletion.model = "gpt"
    chatCompletion.created = 123
    chatCompletion.object = "chat"
    message = MagicMock()
    message.context = {"source": "test"}
    message.content = "response"
    choice = MagicMock()
    choice.message = message
    chatCompletion.choices = [choice]

    result = utils.format_non_streaming_response(chatCompletion, {"meta": 1}, "req-id")
    assert result["choices"][0]["messages"][0]["role"] == "tool"
    assert result["choices"][0]["messages"][1]["role"] == "assistant"


def test_format_non_streaming_response_no_choices():
    chatCompletion = MagicMock()
    chatCompletion.id = "1"
    chatCompletion.model = "gpt"
    chatCompletion.created = 123
    chatCompletion.object = "chat"
    chatCompletion.choices = []

    result = utils.format_non_streaming_response(chatCompletion, {}, "req-id")
    assert result == {}


def test_format_stream_response_with_context():
    chunk = MagicMock()
    chunk.id = "1"
    chunk.model = "gpt"
    chunk.created = 123
    chunk.object = "chat"
    delta = MagicMock()
    delta.context = {"source": "stream"}
    delta.role = "tool"
    choice = MagicMock()
    choice.delta = delta
    chunk.choices = [choice]

    result = utils.format_stream_response(chunk, {"meta": 1}, "req-id")
    assert result["choices"][0]["messages"][0]["role"] == "tool"


def test_format_stream_response_with_content():
    chunk = MagicMock()
    chunk.id = "1"
    chunk.model = "gpt"
    chunk.created = 123
    chunk.object = "chat"

    delta = MagicMock()
    delta.content = "Hello"
    delta.role = "assistant"
    # Ensure delta does NOT have a context attribute
    del delta.context

    choice = MagicMock()
    choice.delta = delta

    chunk.choices = [choice]

    result = utils.format_stream_response(chunk, {}, "req-id")
    assert result["choices"][0]["messages"][0]["content"] == "Hello"
    assert result["choices"][0]["messages"][0]["role"] == "assistant"


def test_format_stream_response_empty():
    chunk = MagicMock()
    chunk.id = "1"
    chunk.model = "gpt"
    chunk.created = 123
    chunk.object = "chat"
    chunk.choices = []

    result = utils.format_stream_response(chunk, {}, "req-id")
    assert result == {}


def test_format_pf_non_streaming_response_valid():
    chatCompletion = {
        "id": "1",
        "response": "Answer",
        "citations": "Refs"
    }
    result = utils.format_pf_non_streaming_response(
        chatCompletion, {}, "response", "citations"
    )
    assert result["choices"][0]["messages"][0]["content"] == "Answer"


def test_format_pf_non_streaming_response_error_key():
    chatCompletion = {"error": "Failure"}
    result = utils.format_pf_non_streaming_response(chatCompletion, {}, "r", "c")
    assert result["error"] == "Failure"


def test_format_pf_non_streaming_response_none():
    result = utils.format_pf_non_streaming_response(None, {}, "r", "c")
    assert "error" in result


def test_format_pf_non_streaming_response_exception():
    badCompletion = {"id": "1", "invalid": object()}
    result = utils.format_pf_non_streaming_response(badCompletion, {}, "invalid", "c")
    assert isinstance(result, dict)


def test_convert_to_pf_format_valid():
    input_json = {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ]
    }
    result = utils.convert_to_pf_format(input_json, "input", "output")
    assert result[0]["inputs"]["input"] == "Hello"
    assert result[0]["outputs"]["output"] == "Hi"

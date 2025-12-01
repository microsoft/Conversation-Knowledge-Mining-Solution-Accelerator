"""Helper functions for processing RAG responses and generating Chart.js-compatible chart data using Azure OpenAI."""

import json
import time
import uuid
import logging
from helpers.azure_openai_helper import get_azure_openai_client
from common.config.config import Config

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def process_rag_response(rag_response, query):
    """
    Parses the RAG response dynamically to extract chart data for Chart.js.
    """
    try:
        config = Config()
        client = get_azure_openai_client()
        system_prompt = """You are an assistant that helps generate valid chart data to be shown using chart.js with version 4.4.4 compatible.
        Include chart type and chart options.
        Pick the best chart type for given data.
        Do not generate a chart unless the input contains some numbers. Otherwise return a message that Chart cannot be generated.
        Only return a valid JSON output and nothing else.
        Verify that the generated JSON can be parsed using json.loads.
        Do not include tooltip callbacks in JSON.
        Always make sure that the generated json can be rendered in chart.js.
        Always remove any extra trailing commas.
        Verify and refine that JSON should not have any syntax errors like extra closing brackets.
        Ensure Y-axis labels are fully visible by increasing **ticks.padding**, **ticks.maxWidth**, or enabling word wrapping where necessary.
        Ensure bars and data points are evenly spaced and not squished or cropped at **100%** resolution by maintaining appropriate **barPercentage** and **categoryPercentage** values."""
        user_prompt = f"""Generate chart data for -
        {query}
        {rag_response}
        """
        logger.info(f">>> Processing chart data for response: {rag_response}")
        completion = client.chat.completions.create(
            model=config.azure_openai_deployment_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        chart_data = completion.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        logger.info(f">>> Generated chart data: {chart_data}")
        return json.loads(chart_data)
    except Exception as e:
        logger.error(f"Error processing RAG response: {e}")
        return {"error": "Chart could not be generated from this data. Please ask a different question."}


async def complete_chat_request(query, last_rag_response=None):
    """
    Completes a chat request by generating a chart from the RAG response.
    """
    if not last_rag_response:
        return {"error": "A previous RAG response is required to generate a chart."}
    # Process RAG response to generate chart data
    chart_data = process_rag_response(last_rag_response, query)
    if not chart_data or "error" in chart_data:
        return {
            "error": "Chart could not be generated from this data. Please ask a different question.",
            "error_desc": str(chart_data),
        }
    logger.info("Successfully generated chart data.")
    return {
        "id": str(uuid.uuid4()),
        "model": "azure-openai",
        "created": int(time.time()),
        "object": chart_data,
    }

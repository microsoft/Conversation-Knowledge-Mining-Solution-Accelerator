import logging


async def stream_processor(response):
    try:
        async for message in response:
            if message.content:
                yield message.content
    except Exception as e:
        logging.error(f"Error processing streaming response: {e}", exc_info=True)
        raise

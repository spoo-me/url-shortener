import asyncio
import json
import aio_pika
from workers.stats_handler import handle_click_event
from workers.async_mongo import init_async_db
import sys
from loguru import logger

logger.remove()

logger.add(
    sys.stdout,
    level="INFO",
    enqueue=True,
    backtrace=True,
    diagnose=False,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
)

RABBITMQ_URL = "amqp://localhost/"
QUEUE_NAME = "stats_queue"


async def StatsWorker():
    # Initialize async MongoDB connection
    await init_async_db()
    logger.info("[*] Async MongoDB initialized.")

    # Connect to RabbitMQ
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)

    logger.info(f"[*] Connected to RabbitMQ, consuming from '{QUEUE_NAME}'...")
    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                try:
                    data = json.loads(message.body)
                    logger.info(
                        f"[x] Received click data for: {data.get('short_code', 'unknown')}"
                    )
                    # Delegate to the async handler
                    await handle_click_event(data)
                except Exception as e:
                    logger.error(f"[!] Error processing message: {e}")
                    # The message will be requeued automatically on failure

    # Cleanup on exit
    await connection.close()


if __name__ == "__main__":
    logger.info("[*] Starting Stats Worker...")
    try:
        asyncio.run(StatsWorker())
    except KeyboardInterrupt:
        logger.error(" [!] Stats Worker stopped by user.")

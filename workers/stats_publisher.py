import pika
import json


def send_to_queue(data):
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()

    channel.queue_declare(queue="stats_queue", durable=True)
    channel.basic_publish(
        exchange="",
        routing_key="stats_queue",
        body=json.dumps(data),
        properties=pika.BasicProperties(
            delivery_mode=2  # make message persistent
        ),
    )

    connection.close()

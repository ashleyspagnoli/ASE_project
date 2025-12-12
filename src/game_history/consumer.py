import pika
import json
import time
import threading
import ssl
from config import RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_CERT_PATH, RABBITMQ_USER, RABBITMQ_PASSWORD
from logic import process_match_data

def consume_game_history():
    print("Starting RabbitMQ consumer thread...", flush=True)
    while True:
        try:
            print(f"Connecting to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT} via SSL...", flush=True)
            
            # Configure SSL connection (always enabled)
            ssl_context = ssl.create_default_context(cafile=RABBITMQ_CERT_PATH)
            ssl_context.check_hostname = True
            ssl_options = pika.SSLOptions(ssl_context, RABBITMQ_HOST)
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
            connection_params = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                ssl_options=ssl_options,
                credentials=credentials
            )
            
            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()
            channel.queue_declare(queue='game_history_queue', durable=True)

            def callback(ch, method, properties, body):
                print("Received match data from RabbitMQ", flush=True)
                try:
                    data = json.loads(body)
                    if process_match_data(data):
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    else:
                        # Log error but ack to avoid infinite loop if data is bad
                        print("Failed to process match data, acking anyway to clear queue", flush=True)
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    print(f"Error processing message: {e}", flush=True)
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue='game_history_queue', on_message_callback=callback)

            print('Waiting for messages. To exit press CTRL+C', flush=True)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            print(f"RabbitMQ connection failed: {e}. Retrying in 5 seconds...", flush=True)
            time.sleep(5)
        except Exception as e:
            print(f"Error in RabbitMQ consumer: {e}. Retrying in 5 seconds...", flush=True)
            time.sleep(5)

def start_consumer():
    # Start consumer in a background thread
    threading.Thread(target=consume_game_history, daemon=True).start()

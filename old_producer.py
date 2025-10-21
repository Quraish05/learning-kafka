# pylint: disable=all
import uuid
import json
from confluent_kafka import Producer

producer = Producer({
    'bootstrap.servers': 'localhost:9092'
})

def delivery_report(err, msg):
    if err:
        print(f"Error: {err}")
    else:
        print(f"Message delivered {msg.value().decode('utf-8')}")
        
order = {
  "order_id": str(uuid.uuid4()),
  "user": 'nicole',
  "item" : 'jam',
  "quantity": 5,
}

value = json.dumps(order).encode('utf-8')

producer.produce(
  topic='orders', 
  value=value,
  callback=delivery_report
)

producer.flush()

import faust

# 1) Define the "shape" of an order
class Order(faust.Record, serializer='json'):
    order_id: int
    user: str
    total: float
    status: str
    ts: str  # ISO timestamp string

# 2) Define the Faust application
# IMPORTANT: aiokafka 0.12.0 has API version compatibility issues with Kafka 4.0.0 cluster setup.
# When Kafka returns metadata with all brokers (9092, 9094, 9096), aiokafka tries to connect to all,
# causing connection failures. 
# 
# Solutions:
# 1. Use single-broker setup (docker-compose.yml) instead of cluster (docker-compose.cluster.yml)
# 2. Or stop kafka-2 and kafka-3 temporarily: docker compose -f docker-compose.cluster.yml stop kafka-2 kafka-3
# 3. Or upgrade aiokafka when a compatible version is available
#
# Topics are pre-created to avoid CreateTopics API version issues.
app = faust.App(
    "orders-stream-app",          # application id (like Kafka Streams app.id)
    broker="kafka://localhost:9092",  # primary broker
)

# 3) Input topic: raw orders
orders_topic = app.topic(
    "food.orders",
    value_type=Order,             # Faust will parse JSON into Order objects
)

# 4) Output topic: running count per user
by_user_topic = app.topic(
    "food.orders.by_user",
    key_type=str,
    value_type=int,
)

# 5) A table is like a distributed, durable dictionary (state store)
orders_per_user = app.Table(
    "orders_per_user",            # table name (backed by internal changelog topic)
    default=int,                  # default for unseen keys is 0
)

# 6) Agent = async function that processes a stream
@app.agent(orders_topic)
async def process(orders):
# For each Order in food.orders:
# if status == "PLACED", increment the per-user count
# emit the new count to food.orders.by_user
# print a nice log line so you can see it working

    async for order in orders:    # orders is an async stream of Order objects
        if order.status == "PLACED":
            # increase per-user count
            orders_per_user[order.user] += 1
            count = orders_per_user[order.user]

            # emit an event to the output topic
            await by_user_topic.send(key=order.user, value=count)

            print(
                f"[stream] user={order.user} count={count} "
                f"(order_id={order.order_id}, total={order.total})"
            )
        else:
            print(f"[stream] ignoring order_id={order.order_id} with status={order.status}")
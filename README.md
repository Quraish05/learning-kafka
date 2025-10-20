# Kafka Order Processing System

A simple Apache Kafka-based order processing system demonstrating producer-consumer architecture for real-time order tracking.

## 📋 Project Overview

This project implements a basic **event-driven architecture** using Apache Kafka to handle order processing. It consists of three main components:

1. **Kafka Broker** (Docker container)
2. **Order Producer** (`producer.py`) - Creates and sends orders
3. **Order Tracker** (`tracker.py`) - Consumes and processes orders

## 🏗️ Architecture Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Producer      │───▶│   Kafka Broker  │───▶│   Consumer       │
│  (producer.py)  │    │  (docker-compose)│    │  (tracker.py)    │
│                 │    │                 │    │                 │
│ Creates orders  │    │ Stores messages │    │ Processes orders │
│ Sends to topic  │    │ in 'orders' topic│    │ Prints tracking  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 File Breakdown

### 1. `docker-compose.yml` - Kafka Infrastructure
**Purpose**: Sets up a Kafka broker using Docker

**Key Components**:
- **Kafka Broker**: Runs on port `9092` (standard Kafka port)
- **KRaft Mode**: Modern Kafka without Zookeeper dependency
- **Single Node**: Simplified setup for development
- **Persistence**: Data stored in Docker volume `kafka_kraft`

**Key Kafka Concepts**:
- **Bootstrap Servers**: Entry point for clients to discover Kafka cluster
- **Listeners**: Network interfaces Kafka listens on
- **Advertised Listeners**: Addresses clients use to connect

### 2. `producer.py` - Order Producer
**Purpose**: Creates order messages and sends them to Kafka

**Flow**:
1. Creates a Kafka Producer instance
2. Generates a sample order with UUID, user, item, and quantity
3. Serializes order to JSON and sends to `orders` topic
4. Uses callback function for delivery confirmation

**Key Concepts**:
- **Producer**: Kafka client that publishes messages
- **Topic**: Named channel where messages are stored (`orders`)
- **Serialization**: Converting Python objects to bytes (JSON → UTF-8)
- **Delivery Report**: Callback confirming message delivery

### 3. `tracker.py` - Order Consumer
**Purpose**: Consumes order messages and processes them

**Flow**:
1. Creates a Kafka Consumer instance
2. Subscribes to `orders` topic
3. Polls for new messages continuously
4. Deserializes and processes each order
5. Prints order details

**Key Concepts**:
- **Consumer**: Kafka client that reads messages
- **Consumer Group**: `order-tracker` - allows multiple consumers to share work
- **Offset Reset**: `earliest` - starts from beginning of topic
- **Polling**: Non-blocking way to check for new messages

## 🚀 How to Run

### Prerequisites
- Docker and Docker Compose
- Python 3.x
- `confluent-kafka` Python package

### Setup Instructions

1. **Install Python Dependencies**:
   ```bash
   pip install confluent-kafka
   ```

2. **Start Kafka Broker**:
   ```bash
   docker-compose up -d
   ```

3. **Run the Consumer** (in one terminal):
   ```bash
   python tracker.py
   ```

4. **Run the Producer** (in another terminal):
   ```bash
   python producer.py
   ```

## 💡 Why Kafka is Effective Here

### 1. **Decoupling**
- Producer and Consumer operate independently
- No direct communication between them
- Easy to add more consumers or producers

### 2. **Reliability**
- Messages are persisted on disk
- Automatic replication (in production)
- Delivery guarantees with acknowledgments

### 3. **Scalability**
- Horizontal scaling of consumers
- High throughput for message processing
- Built-in partitioning for parallel processing

### 4. **Real-time Processing**
- Low latency message delivery
- Stream processing capabilities
- Event-driven architecture

## 🔧 Key Kafka Terminology

| Term | Definition | Example in Project |
|------|------------|-------------------|
| **Broker** | Kafka server that stores messages | Docker container on port 9092 |
| **Topic** | Named channel for messages | `orders` topic |
| **Producer** | Client that sends messages | `producer.py` |
| **Consumer** | Client that reads messages | `tracker.py` |
| **Consumer Group** | Collection of consumers sharing work | `order-tracker` group |
| **Offset** | Position of message in topic | Auto-managed by Kafka |
| **Partition** | Subdivision of topic for parallelism | Single partition (default) |
| **Serialization** | Converting data to bytes | JSON → UTF-8 encoding |

## 🎯 Real-World Applications

This pattern is commonly used for:
- **E-commerce**: Order processing, inventory updates
- **Microservices**: Inter-service communication
- **Data Pipelines**: ETL processes, data streaming
- **Event Sourcing**: Audit trails, state reconstruction
- **IoT**: Sensor data collection and processing

## 🔍 Expected Output

When running the system:

**Producer Output**:
```
Message delivered {"order_id": "123e4567-e89b-12d3-a456-426614174000", "user": "john", "item": "burger", "quantity": 5}
```

**Consumer Output**:
```
Consumer is running & subscribed to orders topic
Message received: burger 5 from john
```

## 🚀 Next Steps

To extend this project:
1. Add multiple consumers for load balancing
2. Implement error handling and retries
3. Add message schemas (Avro/Protobuf)
4. Create a web interface for order management
5. Add database persistence for order history
6. Implement authentication and authorization

---

*This project demonstrates the fundamental concepts of Apache Kafka in a simple, easy-to-understand format.*

# Kafka Order Processing System

A simple Apache Kafka-based order processing system demonstrating producer-consumer architecture for real-time order tracking.

## 📋 Project Overview

This project is a comprehensive learning resource for Apache Kafka, progressing from basic producer-consumer patterns to advanced microservices architecture with distributed tracing. It demonstrates real-world Kafka implementations through hands-on chapters.

**Initial Setup**: Basic event-driven architecture with Kafka broker, producer, and consumer components.

**Advanced Features**: Multi-broker clusters, high-throughput producers, consumer groups, stream processing, schema registry, and observability with OpenTelemetry.

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

## 📚 Chapter Guide

This project is organized into progressive chapters, each building upon previous concepts. Detailed documentation for each chapter is available in the `docs/` directory.

### 🧩 Chapter 1 – Initial Kafka Consumer-Producer Setup

**Goal**: Establish foundational Kafka producer-consumer system with management tools.

**What You'll Learn**:
- Producer-consumer basics with `kafka-python` library
- Environment-based configuration
- Consumer groups and offset tracking
- Management scripts for topics and consumer groups

**Key Files**:
- `producer.py` - Refactored producer with JSON serialization
- `consumer.py` - Consumer with CLI arguments and offset tracking
- `scripts/create_topic.sh` - Topic creation script
- `scripts/describe_topic.sh` - Topic inspection tool
- `scripts/describe_group.sh` - Consumer group monitoring
- `scripts/list_groups.sh` - List all consumer groups

**Key Concepts**: Producer, Consumer, Topic, Consumer Group, Offset, Partition, Bootstrap Server

**Documentation**: See `docs/chp1.md` for detailed explanations.

---

### 🏗️ Chapter 2 – Multi-Broker Kafka Cluster with Partitioning and Failover

**Goal**: Set up production-ready multi-broker cluster with replication and fault tolerance.

**What You'll Learn**:
- 3-broker Kafka cluster setup using KRaft mode (no Zookeeper)
- Replication and high availability (replication factor 3, min ISR 2)
- Service-specific topic organization
- Broker failure handling and automatic failover
- Consumer group rebalancing during failures

**Key Files**:
- `docker-compose.cluster.yml` - Multi-broker cluster configuration
- Service-specific consumers (kitchen, delivery, payments)
- Health check scripts
- Failover demonstration scripts

**Key Concepts**: KRaft Mode, Replication Factor, ISR (In-Sync Replicas), Leader Election, Partition Leadership, Consumer Group Rebalancing

**Documentation**: See `docs/chp2.md` for detailed explanations.

---

### ⚡ Chapter 3 – Multi-Partition Topics & Consumer Groups

**Goal**: Learn to scale Kafka throughput with multiple partitions and observe consumer group behavior.

**What You'll Learn**:
- Creating multi-partition topics (6 partitions)
- High-throughput producer configuration (batching, compression)
- Consumer group partition assignment
- Rebalancing when consumers join/leave
- Monitoring lag and partition distribution

**Key Files**:
- `src/producers/fast_order_producer.py` - Tuned producer with batching and compression
- `src/consumers/group_order_consumer.py` - Consumer with rebalance listener
- `src/consumers/kitchen_worker.py` - Domain-flavored consumer example

**Key Concepts**: Partitions, Throughput Tuning, Consumer Groups, Rebalancing, Lag Monitoring, Batching, Compression

**Documentation**: See `docs/chp3.md` for detailed explanations and code walkthroughs.

---

### 🔍 Chapter 4 – FastAPI Microservice with OpenTelemetry Distributed Tracing

**Goal**: Build microservices with Kafka and implement end-to-end observability.

**What You'll Learn**:
- FastAPI service that produces to Kafka
- Kafka consumer worker service
- OpenTelemetry distributed tracing setup
- W3C traceparent header propagation through Kafka
- Jaeger for trace visualization
- End-to-end trace correlation across services

**Key Files**:
- `src/services/orders_api.py` - FastAPI service with Kafka producer
- `src/services/orders_worker.py` - Kafka consumer worker
- `src/otel.py` - OpenTelemetry setup module
- `scripts/otel-collector-config.yaml` - OTel collector configuration
- `docker-compose.yml` - Updated with OTel Collector and Jaeger

**Key Concepts**: Distributed Tracing, OpenTelemetry, W3C Traceparent, Context Propagation, Span Kinds, Microservices Observability

**Documentation**: See `docs/chp4.md` for detailed explanations and code walkthroughs.

---

### 🔌 Chapter 5 – Kafka Connect Integration

**Goal**: Integrate Kafka Connect for data pipeline operations.

**What You'll Learn**:
- Kafka Connect setup and configuration
- File source and sink connectors
- Connector management via REST API
- Data pipeline patterns
- Reading from and writing to files via Kafka

**Key Files**:
- `connect/connector-file-source.json` - File source connector configuration
- `connect/connector-file-sink.json` - File sink connector configuration
- `scripts/connect-register.sh` - Connector registration script
- `scripts/connect-status.sh` - Connector status monitoring
- `docker-compose.yml` - Kafka Connect service configuration

**Key Concepts**: Kafka Connect, Connectors, Source Connectors, Sink Connectors, Data Pipelines, Connector REST API

**Use Cases**: File-based ETL, database synchronization, log aggregation, data lake ingestion

---

### 📊 Chapter 6 – Kafka Streams with Schema Registry

**Goal**: Implement stream processing with Avro schemas and Schema Registry for type-safe data pipelines.

**What You'll Learn**:
- Faust stream processing framework
- Avro schema definition and serialization
- Schema Registry integration and schema evolution
- Stream transformations and aggregations
- Stateful stream processing with tables
- Building real-time statistics services

**Key Files**:
- `streams/orders_stream_app.py` - JSON-based stream processing application
- `streams/orders_stream_app_avro.py` - Avro-based stream processing with Schema Registry
- `src/services/fast_stats_user.py` - FastAPI service consuming JSON stream results
- `src/services/fast_stats_user_avro.py` - FastAPI service consuming Avro stream results
- `src/services/order_models.py` - Shared Pydantic models
- `src/producers/produce_stream_demo.py` - Demo producer for stream testing
- `docker-compose.yml` - Schema Registry service configuration

**Key Concepts**: Stream Processing, Faust, Avro, Schema Registry, Stream Transformations, Stateful Processing, Stream Tables, Schema Evolution

**Use Cases**: Real-time analytics, event-driven aggregations, stream-to-stream joins, windowed computations

---

## 🚀 Next Steps

To extend this project:
1. Add more stream processing examples
2. Implement error handling and dead letter topics
3. Add authentication and authorization (SASL/SSL)
4. Create a web interface for order management
5. Add database persistence for order history
6. Implement more complex stream processing patterns
7. Add metrics collection (Prometheus integration)

---

*This project demonstrates Apache Kafka concepts from basics to advanced microservices architecture, with detailed documentation and code explanations in each chapter.*

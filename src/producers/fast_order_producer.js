const { Kafka } = require('kafkajs');
const { randomUUID } = require('crypto');

//  Config (via env or defaults)
const BOOTSTRAP = process.env.KAFKA_BOOTSTRAP || 'localhost:9092';
const TOPIC = process.env.TOPIC || 'food.orders';

// Throughput tuning knobs:
// linger_ms: wait up to N ms to batch more messages before a send (bigger batches = better throughput)
const LINGER_MS = parseInt(process.env.LINGER_MS || '20', 10);

// batch_size: max bytes per batch (producer-side buffer). Larger = fewer requests (better throughput).
const BATCH_SIZE = parseInt(process.env.BATCH_SIZE || String(64 * 1024), 10); // 64 KiB

// compression_type: compresses batches over the wire (less bandwidth, better throughput on network)
const COMPRESSION = process.env.COMPRESSION || 'LZ4'; // alt: GZIP, Snappy, Zstd

//  Kafka client and producer construction
// Kafka manages:
// a background IO thread that sends RecordBatches to the leader of each partition
// retries (depending on acks/error) and batch buffering
const kafka = new Kafka({
  clientId: 'fast-order-producer',
  brokers: BOOTSTRAP.split(','), // list of brokers to discover the cluster
  // Note: kafkajs handles compression, batching, and acks differently than python-kafka
});

const producer = kafka.producer({
  // kafkajs equivalent settings:
  //  acks: controlled via transaction or idempotent producer (default is -1 which is "all")
  //  linger_ms: controlled via maxInFlightRequests and retry settings
  //  batch_size: controlled via maxInFlightRequests
  // For throughput optimization:
  maxInFlightRequests: 1, // Ensure ordering (set to higher for throughput)
  idempotent: true, // Ensures exactly-once semantics (equivalent to acks=all)
  compression: COMPRESSION, // Compression type
  // Note: kafkajs doesn't expose linger_ms directly, but batching happens automatically
});

function makeOrder(i) {
  // Sample "domain" payload for our food app
  const restaurants = [
    'Tandoori Tales',
    'Pizza Hub',
    'Bao Bae',
    'Masala Magic',
  ];
  const items = ['biryani', 'pizza', 'wings', 'bao', 'dosa', 'burger', 'chaat'];

  // Random sample of items (1-3 items)
  const numItems = Math.floor(Math.random() * 3) + 1;
  const selectedItems = [];
  const itemsCopy = [...items];
  for (let j = 0; j < numItems; j++) {
    const randomIndex = Math.floor(Math.random() * itemsCopy.length);
    selectedItems.push(itemsCopy.splice(randomIndex, 1)[0]);
  }

  return {
    order_id: randomUUID(),
    seq: i,
    restaurant: restaurants[Math.floor(Math.random() * restaurants.length)],
    items: selectedItems,
    total: Math.round((Math.random() * 30 + 5) * 100) / 100, // Random between 5-35, rounded to 2 decimals
    ts: new Date().toISOString(),
  };
}

async function main() {
  // COUNT: how many messages to send
  const n = parseInt(process.env.COUNT || '50000', 10);

  // USE_KEYS=false → unkeyed → the client's partitioner spreads across partitions (good parallelism).
  // USE_KEYS=true  → supply many distinct keys so the hash spreads across partitions deterministically.
  const useKeys = (process.env.USE_KEYS || 'false').toLowerCase() === 'true';
  const keysSpace = Array.from({ length: 32 }, (_, i) => `k${i}`); // 32 distinct keys => typically well spread across 6 partitions

  await producer.connect();
  console.log('Producer connected');

  const t0 = Date.now();
  const promises = []; // send() returns a Promise; we could inspect for per-record ack if desired

  for (let i = 0; i < n; i++) {
    const order = makeOrder(i);
    const key = useKeys
      ? keysSpace[Math.floor(Math.random() * keysSpace.length)]
      : null;

    // send() is async; messages are enqueued into batches by partition; background thread sends them.
    promises.push(
      producer.send({
        topic: TOPIC,
        messages: [
          {
            key: key,
            value: JSON.stringify(order),
          },
        ],
      })
    );

    // Optional flush cadence to bound memory during huge runs:
    if (i % 5000 === 0 && i > 0) {
      await Promise.all(promises); // Wait for all pending sends
      promises.length = 0; // Clear the array
    }
  }

  // Ensure all messages are out before timing
  await Promise.all(promises);
  await producer.disconnect();

  const dt = (Date.now() - t0) / 1000; // Convert to seconds
  const rate = dt > 0 ? n / dt : n;
  console.log(
    `Sent ${n} messages to ${TOPIC} in ${dt.toFixed(2)}s (${Math.floor(
      rate
    ).toLocaleString()} msg/s).`
  );
}

if (require.main === module) {
  main().catch(error => {
    console.error('Error:', error);
    process.exit(1);
  });
}

module.exports = { makeOrder, producer };

# Known Limitations and Future Work

## Critical Limitations

### 1. No Multi-Instance Coordination (SIGNIFICANT)

**The Problem:**

When multiple applications run independent SOLLOL instances, they **do not coordinate**:

```python
# App 1
pool1 = OllamaPool.auto_configure()
pool1.chat(...)  # Thinks: "Node 1 has 10% CPU load, route there"

# App 2 (same moment)
pool2 = OllamaPool.auto_configure()
pool2.chat(...)  # Thinks: "Node 1 has 10% CPU load, route there"

# Reality: Node 1 now has 50% CPU load, but neither instance knows!
```

**What SHOULD happen:**
1. Both instances detect each other
2. Share real-time cluster state (CPU load, active requests, queue depth)
3. Coordinate routing decisions
4. Aggregate metrics across all instances

**What ACTUALLY happens:**
- Each instance maintains local state only
- No inter-process communication
- No distributed state management
- Routing decisions based on stale information

**Impact:**
- ❌ Resource contention (multiple instances route to same node)
- ❌ Suboptimal load distribution
- ❌ Tail latencies higher than necessary
- ❌ No global priority queue

**Current Workaround:**
Run single SOLLOL gateway, all apps connect via HTTP:
```bash
# One gateway
sollol up --port 8000

# All apps use it
curl http://localhost:8000/api/chat
```

**Why This Is a Real Problem:**
This forces a specific deployment architecture (centralized gateway) rather than allowing distributed operation. It's not a "feature", it's a **limitation**.

---

## What Would Real Coordination Look Like?

### Distributed State Architecture

**Components needed:**

1. **Service Discovery**
   - SOLLOL instances find each other on network
   - Maintain membership list
   - Detect when instances join/leave

2. **Shared Cluster State**
   - Real-time node metrics (CPU, GPU, queue depth)
   - Active request count per node
   - Recent routing decisions
   - Failure state

3. **Coordination Protocol**
   - Distributed lock for routing decisions
   - Eventually-consistent state propagation
   - Conflict resolution

4. **Aggregated Metrics**
   - Global request rate
   - Cluster-wide latency distribution
   - Per-node load across all instances

**Implementation Options:**

#### Option A: Redis-Based Coordination (Lightweight)

```python
class DistributedRouter:
    def __init__(self):
        # Connect to shared Redis
        self.redis = Redis(host='localhost', port=6379)

        # Register this instance
        self.instance_id = str(uuid.uuid4())
        self.redis.sadd('sollol:instances', self.instance_id)

        # Heartbeat
        self.heartbeat_thread = threading.Thread(target=self._heartbeat)
        self.heartbeat_thread.start()

    def _heartbeat(self):
        """Update instance liveness every 5 seconds."""
        while True:
            self.redis.setex(
                f'sollol:instance:{self.instance_id}:alive',
                10,  # TTL: 10 seconds
                '1'
            )
            time.sleep(5)

    def select_optimal_node(self, context):
        # Get current global state
        all_instances = self.redis.smembers('sollol:instances')

        # Aggregate routing data from all instances
        for instance_id in all_instances:
            is_alive = self.redis.get(f'sollol:instance:{instance_id}:alive')
            if not is_alive:
                # Instance dead, remove it
                self.redis.srem('sollol:instances', instance_id)
                continue

            # Get this instance's view of cluster load
            node_loads = self.redis.hgetall(f'sollol:instance:{instance_id}:node_loads')
            # Aggregate with our view
            self._merge_node_loads(node_loads)

        # Now make routing decision with global state
        best_node = self._score_with_global_state(context)

        # Update our routing decision in shared state
        self.redis.hincrby(f'sollol:node:{best_node}:active_requests', 1)

        return best_node
```

**Advantages:**
- ✅ Relatively simple to implement
- ✅ Redis is battle-tested
- ✅ Fast (sub-millisecond operations)
- ✅ Eventually consistent state

**Disadvantages:**
- ⚠️ Redis becomes single point of failure
- ⚠️ Network overhead for every routing decision
- ⚠️ Added complexity in deployment

#### Option B: Gossip Protocol (Decentralized)

```python
class GossipCoordinator:
    """
    Decentralized coordination using gossip protocol.
    No central state store needed.
    """

    def __init__(self):
        self.peers = set()  # Other SOLLOL instances
        self.local_state = {}  # This instance's view

        # Periodically gossip with random peers
        self.gossip_thread = threading.Thread(target=self._gossip_loop)
        self.gossip_thread.start()

    def _gossip_loop(self):
        """Every 1 second, gossip with 3 random peers."""
        while True:
            random_peers = random.sample(self.peers, min(3, len(self.peers)))
            for peer in random_peers:
                # Send our state to peer
                self._send_state_to_peer(peer, self.local_state)

                # Receive peer's state
                peer_state = self._receive_state_from_peer(peer)

                # Merge states
                self._merge_states(peer_state)

            time.sleep(1)

    def _merge_states(self, peer_state):
        """Merge peer's view with ours using vector clocks."""
        for node, metrics in peer_state.items():
            if node not in self.local_state:
                self.local_state[node] = metrics
            else:
                # Keep most recent data (vector clock comparison)
                if metrics['version'] > self.local_state[node]['version']:
                    self.local_state[node] = metrics
```

**Advantages:**
- ✅ No central coordinator
- ✅ Fully decentralized
- ✅ Scales to many instances
- ✅ Resilient to failures

**Disadvantages:**
- ⚠️ Complex to implement correctly
- ⚠️ Eventually consistent (not immediate)
- ⚠️ Convergence time increases with cluster size

#### Option C: Hybrid (Recommended)

**Use etcd/Consul for coordination:**
- Service discovery built-in
- Distributed locks available
- Watch API for state changes
- Production-ready

```python
import etcd3

class EtcdCoordinator:
    def __init__(self):
        self.etcd = etcd3.client(host='localhost', port=2379)

        # Register this instance
        self.instance_id = str(uuid.uuid4())
        self.lease = self.etcd.lease(ttl=10)  # 10 second TTL
        self.etcd.put(
            f'/sollol/instances/{self.instance_id}',
            json.dumps({'started_at': time.time()}),
            lease=self.lease
        )

        # Watch for other instances
        self.etcd.add_watch_callback(
            '/sollol/instances/',
            self._on_instance_change,
            range_end='/sollol/instances0'  # Prefix watch
        )

    def select_optimal_node(self, context):
        # Atomic routing with distributed lock
        with self.etcd.lock('/sollol/routing-lock', ttl=1):
            # Read current global state
            cluster_state = self._get_cluster_state()

            # Make routing decision
            best_node = self._score_nodes(cluster_state, context)

            # Update global state atomically
            self.etcd.put(
                f'/sollol/nodes/{best_node}/active_requests',
                str(cluster_state[best_node]['active_requests'] + 1)
            )

            return best_node
```

**Advantages:**
- ✅ Production-ready (used by Kubernetes)
- ✅ Distributed locks
- ✅ Strong consistency available
- ✅ Built-in leader election

**Disadvantages:**
- ⚠️ Another service to deploy
- ⚠️ Added latency (~5-10ms per routing decision)

---

## Implementation Effort

### Phase 1: Basic Coordination (1-2 weeks)

**Goal:** Multiple instances detect each other and share basic state

**Implementation:**
1. Add Redis dependency
2. Implement instance registration/heartbeat
3. Share node load metrics
4. Aggregate state before routing decisions

**Deliverable:**
- Multiple SOLLOL instances can run concurrently
- They coordinate basic routing
- No resource conflicts

### Phase 2: Advanced Features (2-4 weeks)

**Goal:** Full distributed coordination

**Implementation:**
1. Distributed priority queue (across instances)
2. Request migration (move queued requests between instances)
3. Leader election for cluster-wide tasks
4. Metrics aggregation across instances

**Deliverable:**
- Global priority queue
- Load balancing between instances
- Cluster-wide observability

### Phase 3: Production Hardening (4+ weeks)

**Goal:** Enterprise-grade distributed system

**Implementation:**
1. Failure recovery mechanisms
2. Split-brain detection and resolution
3. Performance optimization (caching, batching)
4. Monitoring and alerting integration

---

## Current State vs. Ideal State

### Current State (v0.3.6)

**Architecture:**
```
App 1 → SOLLOL Instance 1 → Ollama Nodes
App 2 → SOLLOL Instance 2 → Ollama Nodes  ❌ NO COORDINATION
App 3 → SOLLOL Instance 3 → Ollama Nodes
```

**What works:**
- ✅ Single instance routing is intelligent
- ✅ Priority queue within an instance
- ✅ Failover within an instance

**What doesn't work:**
- ❌ No coordination between instances
- ❌ Duplicate routing decisions
- ❌ No global priority queue
- ❌ Stale cluster state

### Ideal State (Future)

**Architecture:**
```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ SOLLOL 1 │────▶│  Redis   │◀────│ SOLLOL 2 │
│          │     │  / etcd  │     │          │
└────┬─────┘     └──────────┘     └────┬─────┘
     │                                  │
     │        Shared Cluster State      │
     │                                  │
     └────────────┬─────────────────────┘
                  │
          ┌───────▼────────┐
          │  Ollama Nodes  │
          └────────────────┘
```

**What works:**
- ✅ Multiple instances coordinate
- ✅ Shared global state
- ✅ No routing conflicts
- ✅ Global priority queue
- ✅ Efficient load distribution

---

## Other Known Limitations

### 2. Single-Machine Benchmarking Can't Prove Performance Gains

**Problem:** Running Docker containers on one machine shares resources
**Impact:** Can't validate intelligent routing improvements
**Solution:** Need multi-node physical cluster
**Status:** Documented in BENCHMARKING.md

### 3. Priority Queue is Async-Only

**Problem:** Synchronous API can't use priority queue features
**Impact:** Sync wrapper bypasses queue
**Solution:** Need thread-safe sync queue implementation
**Status:** Works around with blocking HTTP calls

### 4. No Request Migration

**Problem:** Once routed, request can't move to different node
**Impact:** Sticky to initially-selected node even if better option appears
**Solution:** Implement request cancellation + re-routing
**Status:** Would require significant refactoring

### 5. Learning is Per-Instance, Not Cluster-Wide

**Problem:** Performance history not shared between instances
**Impact:** Each instance learns independently, redundant data
**Solution:** Shared performance metrics store
**Status:** Requires distributed coordination (see #1)

---

## Workarounds for Current Limitations

### For Multi-Instance Coordination

**Option 1:** Use shared gateway (recommended)
```bash
sollol up --port 8000
# All apps connect to http://localhost:8000
```

**Option 2:** Manual node partitioning
```python
# App 1: Only use nodes 1-2
pool1 = OllamaPool(nodes=['http://node1:11434', 'http://node2:11434'])

# App 2: Only use nodes 3-4
pool2 = OllamaPool(nodes=['http://node3:11434', 'http://node4:11434'])

# No overlap = no conflicts
```

**Option 3:** Time-based multiplexing
```python
# App 1: Runs during business hours
# App 2: Runs during off-hours
# No concurrent access = no conflicts
```

---

## Contributing

If you're interested in implementing distributed coordination:

1. **File an issue** describing your use case
2. **Discuss design** - Redis vs gossip vs etcd
3. **Prototype** a minimal working implementation
4. **Submit PR** with tests and documentation

**Priority:** This is a high-priority enhancement for production use cases.

---

## Summary

**The honest assessment:**

SOLLOL v0.3.6 is designed for **single-instance deployment**. Multiple independent instances will conflict on routing decisions because there's no distributed state coordination.

**This is not a feature - it's a limitation.**

For production multi-instance deployments, you currently need:
- Use shared gateway architecture (HTTP-based)
- OR manually partition nodes between instances
- OR accept suboptimal routing with conflicts

Implementing distributed coordination (Redis/etcd/gossip) would solve this, but adds significant complexity. This is documented as future work with clear implementation options outlined above.

# SOLLOL Integration Examples

This directory contains practical examples demonstrating how to integrate SOLLOL into your applications and infrastructure.

## Examples

### 1. `sync_agents.py` - Synchronous Agent Integration

Demonstrates using SOLLOL's synchronous API wrapper with agent frameworks.

**Key concepts:**
- No async/await needed
- Priority-based multi-agent orchestration
- Simple agent workflows
- Error handling

**Run it:**
```bash
python examples/integration/sync_agents.py
```

**Highlights:**
```python
from sollol.sync_wrapper import OllamaPool
from sollol.priority_helpers import Priority

pool = OllamaPool.auto_configure()

# Synchronous call - no async/await!
response = pool.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Hello!"}],
    priority=Priority.HIGH,
    timeout=60
)
```

---

### 2. `priority_mapping.py` - Priority Configuration

Shows how to use SOLLOL's priority system effectively.

**Key concepts:**
- Semantic priority levels (CRITICAL, HIGH, NORMAL, etc.)
- Role-based priority mapping (researcher=8, background=2)
- Task-based priority mapping (interactive=9, batch=1)
- Custom priority schemes
- Dynamic priority calculation

**Run it:**
```bash
python examples/integration/priority_mapping.py
```

**Highlights:**
```python
from sollol.priority_helpers import get_priority_for_role, Priority

# Use role-based mapping
priority = get_priority_for_role("researcher")  # Returns 8

# Or use semantic constants
priority = Priority.HIGH  # Returns 7

# Or calculate dynamically
def get_dynamic_priority(user_tier: str, complexity: str) -> int:
    base = {"free": 3, "premium": 8}[user_tier]
    boost = {"simple": 0, "complex": 2}[complexity]
    return min(base + boost, 10)
```

---

### 3. `load_balancer_wrapper.py` - Infrastructure Integration

Demonstrates wrapping SOLLOL around existing infrastructure.

**Key concepts:**
- Gradual migration from legacy systems
- Backward compatibility
- SOLLOL detection (vs native Ollama)
- Multi-tier routing strategies
- Hybrid legacy/SOLLOL operation

**Run it:**
```bash
python examples/integration/load_balancer_wrapper.py
```

**Highlights:**
```python
class SOLLOLEnhancedLoadBalancer:
    """Wrap SOLLOL around existing node registry."""

    def __init__(self, legacy_registry, enable_sollol=True):
        # Extract nodes from legacy system
        nodes = [{"host": n["host"], "port": n["port"]}
                 for n in legacy_registry.get_available_nodes()]

        # Create SOLLOL pool
        self.sollol_pool = OllamaPool(nodes=nodes)

    def route_request(self, model, messages, use_sollol=True):
        """Can route via SOLLOL or legacy method."""
        if use_sollol:
            return self.sollol_pool.chat(model=model, messages=messages)
        else:
            return self._legacy_routing(model, messages)
```

---

## Common Integration Patterns

### Pattern 1: Synchronous Application → SOLLOL

**Before (direct Ollama):**
```python
import requests

response = requests.post("http://localhost:11434/api/chat", json={
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "Hello"}]
})
```

**After (SOLLOL with intelligent routing):**
```python
from sollol.sync_wrapper import OllamaPool
from sollol.priority_helpers import Priority

pool = OllamaPool.auto_configure()  # Auto-discovers nodes

response = pool.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Hello"}],
    priority=Priority.HIGH  # Gets prioritized
)
```

**Benefits:**
- Automatic load balancing across multiple nodes
- Priority-based scheduling
- Intelligent node selection
- Failover and retry logic

---

### Pattern 2: Multi-Agent System → SOLLOL

**Use case:** Multi-agent framework with different priority levels

```python
from sollol.sync_wrapper import OllamaPool
from sollol.priority_helpers import get_priority_for_role

pool = OllamaPool.auto_configure()

agents = [
    {"name": "Researcher", "role": "researcher"},     # Priority 8
    {"name": "Editor", "role": "editor"},             # Priority 6
    {"name": "Summarizer", "role": "summarizer"},     # Priority 5
]

for agent in agents:
    priority = get_priority_for_role(agent["role"])

    response = pool.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": f"Task for {agent['name']}"}],
        priority=priority
    )

    process_response(agent["name"], response)
```

**Benefits:**
- User-facing agents get higher priority
- Background tasks don't block interactive work
- Fair scheduling with age-based priority boost

---

### Pattern 3: Existing Load Balancer → SOLLOL

**Use case:** Gradual migration from custom load balancer

```python
# Phase 1: Wrap SOLLOL around existing infrastructure
lb = SOLLOLEnhancedLoadBalancer(
    legacy_registry=existing_registry,
    enable_sollol=True
)

# Can still use legacy routing for compatibility
response = lb.route_request(model, messages, use_sollol=False)  # Legacy

# Or use SOLLOL routing for better performance
response = lb.route_request(model, messages, use_sollol=True)   # SOLLOL

# Phase 2: Gradually move all traffic to SOLLOL
# Phase 3: Remove legacy code entirely
```

**Benefits:**
- Low-risk migration path
- Test SOLLOL on subset of traffic
- Easy rollback if needed
- Preserve existing monitoring

---

## SOLLOL Detection

Detect if SOLLOL is running vs native Ollama:

```python
import requests

def is_sollol(url="http://localhost:11434"):
    """Detect SOLLOL vs native Ollama."""

    # Method 1: Check headers
    response = requests.get(url)
    if response.headers.get("X-Powered-By") == "SOLLOL":
        return True

    # Method 2: Check health endpoint
    response = requests.get(f"{url}/api/health")
    if response.json().get("service") == "SOLLOL":
        return True

    return False
```

---

## Priority System Quick Reference

### Semantic Levels
```python
Priority.CRITICAL      # 10 - Mission-critical
Priority.URGENT        #  9 - Fast response needed
Priority.HIGHER        #  8 - Very important
Priority.HIGH          #  7 - Important
Priority.ABOVE_NORMAL  #  6 - Above baseline
Priority.NORMAL        #  5 - Default
Priority.BELOW_NORMAL  #  4 - Below baseline
Priority.LOW           #  3 - Non-urgent
Priority.LOWEST        #  2 - Bulk operations
Priority.BATCH         #  1 - Can wait indefinitely
```

### Predefined Agent Roles
```python
Role              Priority    Use Case
--------------    --------    -------------------------
researcher        8           Interactive research
analyst           8           User-requested analysis
assistant         8           Direct user interaction
critic            7           Critical analysis
reviewer          7           Review and validation
editor            6           Content editing
summarizer        5           Summarization tasks
classifier        5           Classification
background        2           Background tasks
batch             1           Batch processing
```

### Predefined Task Types
```python
Task Type         Priority    Use Case
--------------    --------    -------------------------
interactive       9           Real-time interaction
chat              8           Chat/conversation
query             8           User queries
analysis          7           Analysis tasks
reasoning         7           Complex reasoning
generation        6           Content generation
summarization     5           Summarization
classification    5           Classification
embedding         4           Generate embeddings
indexing          3           Indexing operations
batch             1           Batch processing
```

---

## Running the Examples

### Prerequisites

1. **Install SOLLOL:**
   ```bash
   pip install sollol
   ```

2. **Run Ollama nodes:**
   ```bash
   # On multiple machines in your network
   ollama serve
   ```

3. **Pull models:**
   ```bash
   ollama pull llama3.2
   ```

### Run Examples

```bash
# Synchronous agents
python examples/integration/sync_agents.py

# Priority mapping
python examples/integration/priority_mapping.py

# Load balancer wrapper
python examples/integration/load_balancer_wrapper.py
```

---

## Migration Guide

### From Direct Ollama Calls

**Step 1:** Install SOLLOL
```bash
pip install sollol
```

**Step 2:** Replace direct HTTP calls
```python
# Before
import requests
response = requests.post("http://localhost:11434/api/chat", json={...})

# After
from sollol.sync_wrapper import OllamaPool
pool = OllamaPool.auto_configure()
response = pool.chat(model=..., messages=...)
```

**Step 3:** Add priorities
```python
from sollol.priority_helpers import Priority

response = pool.chat(
    model="llama3.2",
    messages=messages,
    priority=Priority.HIGH  # User-facing tasks get priority
)
```

---

### From Async Ollama Client

**Step 1:** Use async imports
```python
# Before
import ollama
client = ollama.AsyncClient()
response = await client.chat(model=..., messages=...)

# After
from sollol.pool import OllamaPool  # Async version
pool = await OllamaPool.auto_configure()
response = await pool.chat(model=..., messages=..., priority=5)
```

---

### From Custom Load Balancer

See `load_balancer_wrapper.py` for detailed pattern.

**Key steps:**
1. Wrap SOLLOL around existing node registry
2. Test on subset of traffic
3. Gradually increase SOLLOL traffic
4. Monitor performance improvements
5. Remove legacy code

---

## Best Practices

### 1. Priority Assignment

- **User-facing tasks:** Priority 7-10
- **Background processing:** Priority 3-5
- **Batch jobs:** Priority 1-2

### 2. Timeout Configuration

```python
# Interactive tasks - short timeout
pool.chat(..., priority=Priority.HIGH, timeout=30)

# Background tasks - longer timeout
pool.chat(..., priority=Priority.LOW, timeout=300)
```

### 3. Error Handling

```python
try:
    response = pool.chat(model="llama3.2", messages=messages, timeout=60)
except TimeoutError:
    # Handle timeout
    logger.warning("Request timed out")
except Exception as e:
    # Handle other errors
    logger.error(f"Request failed: {e}")
```

### 4. Resource Management

```python
# Create pool once, reuse many times
pool = OllamaPool.auto_configure()

# Use it for all requests
for task in tasks:
    response = pool.chat(...)
```

---

## Troubleshooting

### SOLLOL not detecting nodes

```python
# Check node discovery
pool = OllamaPool.auto_configure()
stats = pool.get_stats()
print(f"Nodes discovered: {stats['num_nodes']}")
```

### Priority not working as expected

```python
# Check priority value
from sollol.priority_helpers import get_priority_for_role

priority = get_priority_for_role("researcher")
print(f"Priority for researcher: {priority}")  # Should be 8
```

### Detection failing

```python
# Verify SOLLOL is running
import requests

response = requests.get("http://localhost:11434/api/health")
print(response.headers.get("X-Powered-By"))  # Should be "SOLLOL"
print(response.json().get("service"))        # Should be "SOLLOL"
```

---

## Additional Resources

- **SOLLOL Documentation:** [README.md](../../README.md)
- **Architecture Guide:** [ARCHITECTURE.md](../../ARCHITECTURE.md)
- **SynapticLlamas Learnings:** [SYNAPTICLLAMAS_LEARNINGS.md](../../SYNAPTICLLAMAS_LEARNINGS.md)

---

## Contributing Examples

Have a useful integration pattern? Submit a PR with:

1. Self-contained example file
2. Documentation in this README
3. Clear use case description
4. Error handling
5. Inline comments

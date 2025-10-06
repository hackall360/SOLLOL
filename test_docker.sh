#!/bin/bash
# SOLLOL Docker Compose Functional Test
# Tests that docker-compose.test.yml creates working Ollama cluster

set -e

echo "======================================================================"
echo "SOLLOL Docker Compose Functional Test"
echo "======================================================================"
echo

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Step 1: Stop any existing containers
echo -e "${YELLOW}Step 1: Cleaning up existing containers...${NC}"
docker compose -f docker-compose.test.yml down 2>/dev/null || true
echo

# Step 2: Start the cluster
echo -e "${YELLOW}Step 2: Starting 3-node Ollama cluster...${NC}"
docker compose -f docker-compose.test.yml up -d

# Wait for containers to start
echo "Waiting 10 seconds for containers to initialize..."
sleep 10
echo

# Step 3: Check container status
echo -e "${YELLOW}Step 3: Checking container status...${NC}"
docker compose -f docker-compose.test.yml ps
echo

# Step 4: Test connectivity to each node
echo -e "${YELLOW}Step 4: Testing connectivity to all nodes...${NC}"

test_node() {
    local port=$1
    local node_name=$2

    echo -n "Testing ${node_name} (port ${port})... "

    if curl -s http://localhost:${port}/api/tags >/dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        return 1
    fi
}

# Test each node
test_node 11435 "ollama-1" || exit 1
test_node 11436 "ollama-2" || exit 1
test_node 11437 "ollama-3" || exit 1
echo

# Step 5: Check models on each node
echo -e "${YELLOW}Step 5: Checking available models...${NC}"
for port in 11435 11436 11437; do
    echo "Node on port ${port}:"
    curl -s http://localhost:${port}/api/tags | jq -r '.models[] | "  - \(.name)"' 2>/dev/null || echo "  (no models)"
done
echo

# Step 6: Optional - Pull a small model for testing
echo -e "${YELLOW}Step 6: Pull test model (optional)${NC}"
read -p "Pull tinyllama model to all nodes? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Pulling tinyllama to all nodes (this may take a few minutes)..."

    for port in 11435 11436 11437; do
        echo "  Pulling to node on port ${port}..."
        curl -s http://localhost:${port}/api/pull -d '{"name": "tinyllama"}' &
    done

    wait
    echo -e "${GREEN}✓ Model pull initiated on all nodes${NC}"
    echo "  (Models will continue downloading in background)"
    echo
fi

# Step 7: Test request (if model available)
echo -e "${YELLOW}Step 7: Test sample request${NC}"
read -p "Test a chat request? Requires a model to be available. (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter model name (e.g., tinyllama): " model_name

    echo "Sending test request to ollama-1..."
    response=$(curl -s http://localhost:11435/api/chat \
        -d "{\"model\": \"${model_name}\", \"messages\": [{\"role\": \"user\", \"content\": \"Say hello\"}], \"stream\": false}" \
        2>/dev/null)

    if echo "$response" | jq -e '.message.content' >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Request successful!${NC}"
        echo "Response:"
        echo "$response" | jq -r '.message.content'
    else
        echo -e "${RED}✗ Request failed${NC}"
        echo "Response: $response"
    fi
    echo
fi

# Summary
echo "======================================================================"
echo -e "${GREEN}Docker Compose Functional Test Complete!${NC}"
echo "======================================================================"
echo
echo "Your 3-node Ollama cluster is running:"
echo "  - ollama-1: http://localhost:11435"
echo "  - ollama-2: http://localhost:11436"
echo "  - ollama-3: http://localhost:11437"
echo
echo "To stop the cluster:"
echo "  docker compose -f docker-compose.test.yml down"
echo
echo "To view logs:"
echo "  docker compose -f docker-compose.test.yml logs -f"
echo

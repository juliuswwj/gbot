#!/bin/bash
# Remove set -e to handle optional compilation failures
# set -e 

echo "=== gbot Testing & Compilation Script ==="

# 1. Compile eBPF if clang is available
if command -v clang &> /dev/null; then
    echo "Compiling eBPF kernel code..."
    ARCH=$(uname -m)
    INCLUDE_PATH="-I/usr/include/${ARCH}-linux-gnu"
    
    # Try to find libbpf headers
    if [ -d "/usr/include/bpf" ]; then
        INCLUDE_PATH="${INCLUDE_PATH} -I/usr/include"
    fi

    # Execute clang compilation
    if clang -O2 -target bpf ${INCLUDE_PATH} -c src/gmon/ebpf/gmon.bpf.c -o src/gmon/ebpf/gmon.bpf.o 2>/dev/null; then
        echo "eBPF compilation successful: src/gmon/ebpf/gmon.bpf.o"
    else
        echo "WARNING: eBPF compilation failed (missing headers or incompatible system). Skipping."
        echo "Note: Production systems (RPi 5) require linux-headers and libbpf-dev."
    fi
else
    echo "WARNING: clang not found. Skipping eBPF compilation."
fi

# 2. Run Python Unit Tests
echo "Running Python Unit Tests..."
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
if python3 -m unittest discover tests; then
    echo "=== All Python unit tests passed successfully ==="
else
    echo "ERROR: Python unit tests failed."
    exit 1
fi

# 3. Automated Integration Test (Zoho Webhook & Gemini Brain)
echo "Running Automated Integration Test..."
CONFIG_DIR="$HOME/.gbot"
export GBOT_CONFIG_PATH="$CONFIG_DIR/config.yml"

if [ ! -f "$CONFIG_DIR/config.yml" ]; then
    echo "SKIP: Integration test skipped because config.yml is missing in $CONFIG_DIR."
    exit 0
fi

echo "Starting gbot in background..."
PYTHONPATH=$(pwd)/src python3 src/gbot/main.py -test &
GBOT_PID=$!

# Give it a few seconds to start the web server
sleep 5

echo "Sending simulated Zoho Email Webhook to /bot/mail..."
TOKEN=$(grep "webhook_token:" "$GBOT_CONFIG_PATH" | awk '{print $2}' | tr -d '"')
if [ -z "$TOKEN" ]; then TOKEN="test_token"; fi

curl -s -X POST http://localhost:8080/bot/mail \
     -H 'Content-Type: application/json' \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"from": "wwj@ham2.me", "subject": "Test Command", "content": "Ping", "id": "test_msg_123"}'

echo ""
echo "Waiting for gbot to finish processing..."
wait $GBOT_PID

echo "=== gbot tests finished ==="

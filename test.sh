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
    echo "=== All Python tests passed successfully ==="
else
    echo "ERROR: Python tests failed."
    exit 1
fi

echo "=== gbot test script finished ==="

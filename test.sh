#!/bin/bash
set -e

echo "=== gbot Testing & Compilation Script ==="

# 1. Compile eBPF if clang is available
if command -v clang &> /dev/null; then
    echo "Compiling eBPF kernel code..."
    clang -O2 -target bpf -c src/gmon/ebpf/gmon.bpf.c -o src/gmon/ebpf/gmon.bpf.o
    echo "eBPF compilation successful: src/gmon/ebpf/gmon.bpf.o"
else
    echo "WARNING: clang not found. Skipping eBPF compilation (required for production)."
fi

# 2. Run Python Unit Tests
echo "Running Python Unit Tests..."
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python3 -m unittest discover tests

echo "=== All tests passed successfully ==="

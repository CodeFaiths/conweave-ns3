#!/bin/bash

# Kill network-load-balance processes in current container only

echo "Searching for network-load-balance processes in current container..."

# Get current container's processes only (using /proc to ensure we're in container scope)
pids=""
for pid in $(ls /proc 2>/dev/null | grep -E '^[0-9]+$'); do
    if [ -f "/proc/$pid/cmdline" ] 2>/dev/null; then
        cmdline=$(cat "/proc/$pid/cmdline" 2>/dev/null | tr '\0' ' ')
        if echo "$cmdline" | grep -q "network-load-balance"; then
            pids="$pids $pid"
        fi
    fi
done

pids=$(echo $pids | xargs)  # trim whitespace

if [ -z "$pids" ]; then
    echo "No network-load-balance processes found in current container."
    exit 0
fi

# Show processes before killing
echo "Found the following processes:"
for pid in $pids; do
    ps -p $pid -o pid,ppid,etime,cmd 2>/dev/null | tail -n +2
done
echo ""

# Count processes
count=$(echo "$pids" | wc -w)
echo "Total: $count process(es)"
echo ""

# Kill processes one by one
echo "Killing processes..."
for pid in $pids; do
    kill -9 $pid 2>/dev/null && echo "  Killed PID $pid" || echo "  Failed to kill PID $pid"
done

echo ""
echo "✓ Done."


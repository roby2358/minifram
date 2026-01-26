# Run the first model
MODEL=`ollama list 2>/dev/null | tail -n +2 | awk '{print $1}'`

echo "ollama run $MODEL "hello" --keepalive -1m"

ollama run $MODEL "hello" --keepalive -1m

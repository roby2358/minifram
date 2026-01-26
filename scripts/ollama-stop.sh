ollama ps 2>/dev/null | tail -n +2 | awk '{print $1}' | xargs -r -n1 ollama stop

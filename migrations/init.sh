#!/bin/bash
max_retries=10
wait_time=5  # seconds
retry_count=0

while (( retry_count < max_retries ))
do
  migrate -source file://scripts -database "$POSTGRES_CONNECTION_STRING" up

  # Capture the exit code of the migrate command
  exit_code=$?

  # Check if the exit code is 0 (success)
  if (( exit_code == 0 )); then
    echo "Migration succeeded."
    exit 0
  else
    (( retry_count++ ))
    echo "Migration failed . Retrying  (attempt ($retry_count/$max_retries) in $wait_time seconds..."
    sleep "$wait_time"
  fi
done

echo "Migration failed after $max_retries retries."
exit 1

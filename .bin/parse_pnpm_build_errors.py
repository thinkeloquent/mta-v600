#!/usr/bin/env python3
"""
Parse pnpm build error logs and convert to JSONL format.

Usage:
    python3 .bin/parse_errors.py

Input:  logs/pnpm-build-error.log
Output: logs/pnpm-build-errors.jsonl

Each output line contains a JSON object with:
    - project: The internal package name (e.g., @internal/my-package)
    - file: Source file path
    - line: Line number of the error
    - error_code: TypeScript error code (e.g., TS2345)
    - message: Full error message (including multi-line continuations)
"""
import re
import json
import os

log_file_path = "logs/pnpm-build-error.log"
output_file_path = "logs/pnpm-build-error.jsonl"

try:
    with open(log_file_path, "r") as f:
        log_content = f.read()
except FileNotFoundError:
    print(f"Error: Log file not found at {log_file_path}")
    exit(1)

jsonl_output = []

# Regex to capture project, file, line, column, error code, and message
# It also handles multi-line error messages by looking for lines that start with '  Type ' or '    Argument of type'
# and appending them to the previous error message.

# Initialize variables to hold current error details for multi-line errors
current_error = None

for line in log_content.splitlines():
    # Attempt to match a new error message line
    match = re.match(r"^(@internal\/[a-zA-Z0-9_-]+): ([^:]+)\((\d+),(\d+)\): error (TS\d+): (.*)$", line)

    if match:
        # If a new error is found, and there was a previous multi-line error, add it to the output
        if current_error:
            jsonl_output.append(json.dumps(current_error))

        project = match.group(1).strip()
        file_path = match.group(2).strip()
        line_num = int(match.group(3))
        # col_num = int(match.group(4)) # Not explicitly asked for but captured
        error_code = match.group(5).strip()
        message = match.group(6).strip()

        current_error = {
            "project": project,
            "file": file_path,
            "line": line_num,
            "error_code": error_code,
            "message": message
        }
    elif current_error and (
        line.strip().startswith("Type '") or
        line.strip().startswith("Argument of type") or
        line.strip().startswith("Overload") or
        line.strip().startswith("Types of parameters") or
        line.strip().startswith("Target signature provides too few arguments") or
        line.strip().startswith("Non-abstract class") or
        line.strip().startswith("Object literal may only specify known properties") or
        line.strip().startswith("Property") or
        line.strip().startswith("Module") or
        line.strip().startswith("Expected") or
        line.strip().startswith("Implicitly") or
        line.strip().startswith("Object is possibly 'undefined'") or
        line.strip().startswith("Missing the following properties") or
        line.strip().startswith("Conversion of type") or
        line.strip().startswith("Index signature for type") or
        line.strip().startswith("must have a '[Symbol.asyncIterator]()' method")
    ):
        # This is a continuation of a multi-line error message
        current_error["message"] += " " + line.strip()
    elif current_error and not line.strip(): # if line is empty and there's a current error, append it as a separator for better readability.
        current_error["message"] += " " + line.strip()
    elif current_error: # If the line doesn't match an error pattern or a recognized continuation, and there's a current error, finalize it.
        jsonl_output.append(json.dumps(current_error))
        current_error = None # Reset for the next potential error

# Add the last error if it exists
if current_error:
    jsonl_output.append(json.dumps(current_error))

# Calculate total and deduplicated error counts
total_errors = len(jsonl_output)
unique_errors = set()
for json_line in jsonl_output:
    error = json.loads(json_line)
    unique_key = (error["file"], error["line"], error["error_code"])
    unique_errors.add(unique_key)
dedup_errors = len(unique_errors)

# Ensure the directory exists
os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

with open(output_file_path, "w") as f:
    for json_line in jsonl_output:
        f.write(json_line + "\n")

print(f"Errors consolidated into {output_file_path}")
print(f"Errors found: {total_errors} total / {dedup_errors} unique")

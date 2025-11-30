#!/usr/bin/env python3
"""Simple test job for variance analysis."""
import os

# Create predictable output file
with open('test-output.txt', 'w') as f:
    f.write('Test job completed successfully\n')
    f.write(f'Timestamp: {os.environ.get("TIMESTAMP", "unknown")}\n')
    f.write('Operations: file_creation, text_output\n')

print("Simple test job: COMPLETED")
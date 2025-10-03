---
name: Bug Report
about: Report a bug or unexpected behavior
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description

A clear and concise description of what the bug is.

## To Reproduce

Steps to reproduce the behavior:

1. Configure SOLLOL with '...'
2. Send request '...'
3. Observe '...'
4. See error

## Expected Behavior

A clear and concise description of what you expected to happen.

## Actual Behavior

What actually happened.

## Environment

- **SOLLOL Version**: [e.g., v1.0.0 or commit hash]
- **Python Version**: [e.g., 3.11.5]
- **Ray Version**: [e.g., 2.9.0]
- **Dask Version**: [e.g., 2024.1.0]
- **Ollama Version**: [e.g., 0.1.17]
- **OS**: [e.g., Ubuntu 22.04, macOS 14.0]
- **Hardware**: [e.g., GPU: RTX 3090, CPU: 32 cores]

## Configuration

```python
# Your SOLLOL configuration
config = SOLLOLConfig(
    ray_workers=4,
    hosts=["..."],
    # ... other config
)
```

## Logs

```
Paste relevant logs here
```

## Additional Context

Add any other context about the problem here, such as:
- Screenshots
- Error traces
- Network diagrams
- Reproducible examples

## Possible Solution

(Optional) If you have ideas on how to fix this, please describe them here.

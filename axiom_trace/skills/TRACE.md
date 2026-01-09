# Axiom Trace - Claude Skill

> **This skill teaches Claude how to use axiom-trace for recording and searching agent traces.**

---

## Installation Check

```python
# Verify axiom-trace is installed
from axiom_trace import trace
print(f"axiom-trace ready")
```

---

## Quick API Reference

| Method | Purpose | Example |
|--------|---------|---------|
| `trace.log(msg)` | Simple log | `trace.log("Starting task")` |
| `trace.thought(reasoning)` | Record thinking | `trace.thought("Need to parse JSON")` |
| `trace.tool(name, args)` | Record tool call | `trace.tool("read_file", {"path": "x.py"})` |
| `trace.done(result)` | Record completion | `trace.done("Created 3 files")` |
| `trace.error(msg, exc)` | Record failure | `trace.error("Failed", e)` |
| `trace.input(text)` | Record user input | `trace.input("Build an API")` |
| `trace.search(query)` | Semantic search | `trace.search("authentication")` |
| `trace.context(query)` | Get past context | `trace.context("REST API patterns")` |

---

## When to Use Each Method

### `trace.thought(reasoning)` - For Planning & Decisions

Use when the agent is **thinking**, **planning**, or **making decisions**:

```python
trace.thought("User wants a REST API - need to design endpoints first")
trace.thought("Should use FastAPI for async support")
trace.thought("Need authentication before user routes")
```

### `trace.tool(name, args)` - For External Actions

Use when **calling tools**, **running commands**, or **making API calls**:

```python
trace.tool("read_file", {"path": "requirements.txt"})
trace.tool("write_file", {"path": "api.py", "content": "..."})
trace.tool("run_command", {"cmd": "pytest"})
trace.tool("web_search", {"query": "FastAPI authentication"})
```

### `trace.done(result)` - For Successful Completion

Use when a **task or subtask completes successfully**:

```python
trace.done("Created REST API with 4 endpoints")
trace.done("All tests passing")
trace.done("Deployed to production")
```

### `trace.error(msg, exception)` - For Failures

Use when **something goes wrong**:

```python
try:
    result = risky_operation()
except Exception as e:
    trace.error("Operation failed", e)
```

---

## Agent Retrospection Patterns

### Pattern 1: Find Relevant Past Work

```python
# Before starting a new task, check if you've done something similar
past_work = trace.search("REST API authentication", limit=5)

if past_work:
    trace.thought(f"Found {len(past_work)} relevant past traces")
    for frame in past_work:
        print(f"Past: {frame['content'].get('reasoning', '')}")
```

### Pattern 2: Get Context for Current Task

```python
# Get formatted context string for prompts
context = trace.context("building user management")

trace.thought(f"Based on past experience: {context}")
```

### Pattern 3: Learn from Past Errors

```python
# Find past errors for similar tasks
past_errors = trace.search("error database", limit=3)

if past_errors:
    trace.thought("Previously encountered database errors - will add retry logic")
```

### Pattern 4: Track Causality

```python
# Link related actions
thought_id = trace.thought("Need to create user model")
trace.tool("write_file", {"path": "models/user.py"}, caused_by=thought_id)
```

---

## Auto-Trace Decorator

For automatic function tracing:

```python
from axiom_trace import auto_trace

@auto_trace
def fetch_user_data(user_id: int):
    # Function calls are automatically traced
    return db.get_user(user_id)

# Captures: function name, arguments, return value, timing, exceptions
```

---

## CLI Commands

```bash
# View recent traces
axiom log

# Watch traces in real-time  
axiom watch

# Search traces
axiom query --prompt "authentication error" --limit 10

# Verify integrity
axiom verify --vault .axiom_trace
```

---

## Full Workflow Example

```python
from axiom_trace import trace

# 1. Record user request
trace.input("Build a REST API for user management")

# 2. Think about approach
trace.thought("Need endpoints: GET/POST/PUT/DELETE users")
trace.thought("Should add authentication middleware")

# 3. Execute with tool calls
trace.tool("write_file", {"path": "api/users.py"})
trace.tool("write_file", {"path": "api/auth.py"})
trace.tool("run_command", {"cmd": "pytest tests/"})

# 4. Record completion
trace.done("Created user management API with 4 endpoints and auth")

# 5. Later - search past work
similar = trace.search("REST API user management")
context = trace.context("API authentication patterns")
```

---

## Trace Storage

Traces are saved to `.axiom_trace/` in the working directory:

```
.axiom_trace/
├── frames.jsonl       # Traces (one JSON per line)
├── vault.manifest.json
├── vault_index.json   # Search index
└── vault.mv2          # Memvid video index
```

---

## Frame Structure

Each trace creates a frame with these fields:

```json
{
  "frame_id": "uuid",
  "timestamp": "ISO-8601",
  "event_type": "thought|tool_call|error|...",
  "content": {
    "text": "Human-readable text",
    "input": "What prompted this",
    "output": "What was produced",
    "reasoning": "Why this action"
  },
  "success": true,
  "artifacts": ["files/created.py"],
  "caused_by": "parent-frame-id"
}
```

---

## Best Practices

1. **Always trace thoughts** before actions - creates clear reasoning chains
2. **Use descriptive tool names** - makes search more effective
3. **Record both success and failure** - learn from errors
4. **Search before starting** - leverage past experience
5. **Link related actions** with `caused_by` - track causality

---

## This skill requires: `pip install axiom-trace`

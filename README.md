# Persistent Priority Queue

A priority queue (Python) whose state survives process restarts. Persistence
is **file-based** (a JSON file on disk), so the project runs with **zero
external dependencies / no database server required**.

## Project structure

```
persistent-priority-queue/
├── README.md
├── module.py        # main implementation (PersistentPriorityQueue)
└── test_module.py   # unit tests covering all required operations
```

## Requirements

- Python 3.7+ (standard library only — no `pip install` needed).

## Running the demo

`module.py` has a small `__main__` block that exercises every operation,
including simulating a process restart by creating a second queue instance
pointed at the same storage file:

```bash
python3 module.py
```

## Running the tests

```bash
python3 -m unittest test_module.py -v
```

## Usage

```python
from module import PersistentPriorityQueue

pq = PersistentPriorityQueue(storage_path="my_queue.json")

id_a = pq.insert(priority=5, value="task-A")
id_b = pq.insert(priority=1, value="task-B")

pq.peek("min")            # -> (id_b, 1, "task-B"), does not remove it
pq.update(id_a, new_priority=0)
pq.extract_min()          # -> (id_a, 0, "task-A"), removes it
pq.delete(id_b)            # -> True
pq.is_empty()               # -> True
```

If `my_queue.json` already exists, the queue is rebuilt from it on
construction, so restarting the process (or even just creating a new
`PersistentPriorityQueue("my_queue.json")` in another script) picks up
exactly where things left off.

## API

| Method | Description |
|---|---|
| `insert(priority, value=None, item_id=None)` | Adds a new item, returns its `item_id` (auto-generated UUID if not supplied). |
| `extract_min()` | Removes & returns `(item_id, priority, value)` of the smallest-priority item, or `None` if empty. |
| `extract_max()` | Same, but for the largest-priority item. |
| `peek(mode="min"\|"max")` | Returns the min/max item without removing it. |
| `update(item_id, new_priority=None, new_value=None)` | Changes an existing item's priority and/or value. Returns `True`/`False`. |
| `delete(item_id)` | Removes an item by id without extracting it. Returns `True`/`False`. |
| `is_empty()` | O(1) check. |

## Implementation notes

A single binary heap only ever gives efficient access to one end of the
ordering, and doesn't support arbitrary-key updates/deletes cheaply on its
own. Since this assignment needs `extract_min`, `extract_max`, `update`, and
`delete` all together, the queue is built from three pieces:

1. **A min-heap** of `(priority, seq, item_id)` — Python's `heapq`.
2. **A max-heap** of `(-priority, seq, item_id)` — the same `heapq`, with
   priorities negated (or reverse-wrapped, for non-numeric priorities) so
   the smallest tuple is really the largest priority.
3. **A dict `entries`**: `item_id -> {priority, value, valid}`, which is the
   single source of truth for what's actually in the queue *right now*.

Both heaps hold references to every item ever inserted, including stale
ones. When popping either heap, a node is discarded ("lazily deleted") if
it no longer matches the current live entry for that id — i.e. the item was
deleted, or updated to a different priority after that heap node was
pushed. This is the classic **lazy-deletion, dual-heap "indexed priority
queue"** technique. Whenever a heap accumulates more stale nodes than live
items, it's rebuilt from `entries`, so cost stays amortized `O(log n)` per
operation over any sequence of operations, and memory never grows
unboundedly from stale nodes.

A monotonically increasing sequence number is embedded in every heap tuple
purely so tuple comparisons are always well-defined (equal priorities break
ties by insertion order, and never fall through to comparing `item_id`
values of mixed types).

### Complexity (n = number of live items)

| Operation | Cost |
|---|---|
| `insert` | O(log n) amortized |
| `extract_min` / `extract_max` | O(log n) amortized |
| `peek` | O(log n) amortized (non-destructive) |
| `update` | O(log n) amortized |
| `delete` | O(log n) amortized |
| `is_empty` | O(1) |

### Persistence

The full state (`entries`, i.e. every live item's priority + value) is
written to `storage_path` after every mutating call, as JSON. Writes are
atomic: state is written to a temp file in the same directory, then
`os.replace()`d over the real file, so a crash mid-write can never leave a
corrupted store on disk. On construction, if `storage_path` already exists,
both heaps are rebuilt from the persisted entries.

**Swapping in PostgreSQL instead of the file backend:** the design maps
directly onto a single table,

```sql
CREATE TABLE pq_entries (
    id        TEXT PRIMARY KEY,
    priority  DOUBLE PRECISION NOT NULL,
    value     JSONB,
    valid     BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX idx_pq_entries_priority ON pq_entries (priority) WHERE valid;
```

`insert`/`update`/`delete` become `INSERT` / `UPDATE` / soft-`DELETE`
statements, and `extract_min` / `extract_max` become

```sql
SELECT id, priority, value FROM pq_entries
WHERE valid ORDER BY priority ASC  LIMIT 1;   -- min
SELECT id, priority, value FROM pq_entries
WHERE valid ORDER BY priority DESC LIMIT 1;   -- max
```

followed by marking the row invalid (or deleting it) in the same
transaction. The in-memory dual-heap layer in `module.py` was kept
because it makes the queue usable as a fast, dependency-free
in-process structure while still satisfying the "persisted" requirement,
and it keeps the assignment trivially runnable for grading without a
database server to provision.

## Real-world use cases for priority queues

- **OS process/task scheduling** — the scheduler always dequeues the
  highest-priority runnable process/thread next (this project's `insert` +
  `extract_max` + `update`, for priority boosting/aging, map directly onto
  this).
- **Job/task queues in backend systems** — e.g. a background-job worker
  pool where jobs carry priorities (or deadlines) and workers always pull
  the most urgent job (`extract_min` on a "deadline" priority).
- **Bandwidth/QoS packet scheduling in networking** — routers prioritize
  packets (e.g. VoIP over bulk transfer) using priority queues.
- **Event-driven simulation** — a discrete-event simulator keeps all
  pending events in a priority queue ordered by timestamp, and needs to
  cancel/reschedule (`delete`/`update`) events as the simulation state
  changes.
- **Load balancers / rate limiters** — routing requests to the
  least-loaded server first is an `extract_min` over live load scores that
  get `update`d as load changes.
- best-first search in games & pathfinding** — the open set is a
  priority queue ordered by estimated cost, with nodes' priorities
  frequently `update`d as cheaper paths to them are discovered.

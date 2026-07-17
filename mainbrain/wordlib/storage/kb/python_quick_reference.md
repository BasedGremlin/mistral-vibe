# Python Quick Reference (3.10+)

## Data Structures

### List Operations
```python
lst = [3, 1, 4, 1, 5, 9]
lst.sort()                          # In-place
sorted_lst = sorted(lst)            # New list
lst.sort(key=lambda x: -x)         # Reverse sort
lst = [x**2 for x in range(10) if x % 2 == 0]  # Comprehension
flat = [x for sub in nested for x in sub]       # Flatten
```

### Dict Operations
```python
d = {"a": 1, "b": 2}
d.get("c", 0)                       # Safe get with default
d.setdefault("c", []).append(1)     # Get or create
{k: v for k, v in d.items() if v > 1}  # Dict comprehension
merged = {**d1, **d2}               # Merge (d2 wins on conflict)
# Counter pattern:
from collections import Counter, defaultdict
counts = Counter(["a", "b", "a", "c"])  # {"a": 2, "b": 1, "c": 1}
```

### Dataclasses
```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class Config:
    name: str
    port: int = 8080
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.port < 1024:
            raise ValueError("Port must be > 1024")
```

---

## File I/O

### Pathlib (preferred over os.path)
```python
from pathlib import Path

p = Path("/home/user/data")
p.mkdir(parents=True, exist_ok=True)
p / "file.txt"                      # Join paths
p.glob("*.py")                      # Glob
p.rglob("*.md")                     # Recursive glob
p.exists(), p.is_file(), p.is_dir()
p.read_text(encoding="utf-8")
p.write_text("content", encoding="utf-8")
p.stat().st_size                    # File size in bytes
p.stem, p.suffix, p.name, p.parent
list(p.iterdir())                   # List directory
```

### JSON
```python
import json
data = json.loads(text)             # str -> dict
text = json.dumps(data, indent=2)   # dict -> str
# File:
with open("data.json", "r") as f:
    data = json.load(f)
with open("data.json", "w") as f:
    json.dump(data, f, indent=2)
```

---

## Error Handling

### Custom Exceptions
```python
class WordlibError(Exception):
    """Base exception for WORDLIB."""

class ConfigError(WordlibError):
    def __init__(self, field: str, msg: str):
        super().__init__(f"Config error in '{field}': {msg}")
        self.field = field
```

### Context Managers
```python
from contextlib import contextmanager, suppress

@contextmanager
def temp_file(suffix=".tmp"):
    path = Path(f"/tmp/temp{suffix}")
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)

# Suppress specific errors:
with suppress(FileNotFoundError):
    Path("missing.txt").unlink()
```

---

## Concurrency

### Threading (I/O bound)
```python
import threading

def worker(item):
    # process item
    pass

threads = [threading.Thread(target=worker, args=(item,)) for item in items]
for t in threads: t.start()
for t in threads: t.join()

# With lock:
lock = threading.Lock()
with lock:
    shared_resource.update()
```

### Subprocess
```python
import subprocess

# Simple command
result = subprocess.run(["ls", "-la"], capture_output=True, text=True, timeout=10)
result.stdout, result.returncode

# Long-running background process
proc = subprocess.Popen(["python", "server.py"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT)
# Later:
proc.terminate()
proc.wait()

# Windows hidden window
flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
proc = subprocess.Popen(cmd, creationflags=flags)
```

---

## Type Hints (3.10+)

```python
from typing import Optional, Union, Any, Callable
from collections.abc import Iterator, Generator

def process(items: list[str]) -> dict[str, int]:  # 3.9+ lowercase generics
    return {item: len(item) for item in items}

def maybe(value: str | None) -> str:              # 3.10+ union syntax
    return value or "default"

type Point = tuple[float, float]                   # 3.12+ type alias
```

---

## Useful Standard Library

```python
# itertools
from itertools import chain, islice, groupby, product, combinations
list(chain([1,2], [3,4]))           # [1, 2, 3, 4]
list(islice(range(100), 5, 15))     # [5..14]

# functools
from functools import lru_cache, partial, reduce
@lru_cache(maxsize=128)
def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)

# datetime
from datetime import datetime, timedelta
now = datetime.now()
now.isoformat()
now + timedelta(days=7)
datetime.fromisoformat("2026-01-15T10:30:00")

# hashlib
import hashlib
hashlib.sha256(b"data").hexdigest()

# secrets (cryptographically secure)
import secrets
secrets.token_hex(16)               # random hex string
secrets.token_urlsafe(32)
```

---

## Flask Patterns

```python
from flask import Flask, request, jsonify, g

app = Flask(__name__)

# Before every request
@app.before_request
def load_user():
    g.user = get_current_user()

# JSON error responses
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Not found"}), 404
    return render_template("404.html"), 404

# Request parsing
data = request.get_json(silent=True) or {}  # Never throws
query = request.args.get("q", "")
files = request.files.get("upload")
```

---

## SQLite (standard library)

```python
import sqlite3

con = sqlite3.connect("data.db")
con.row_factory = sqlite3.Row  # Access columns by name
cur = con.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, text TEXT)")
cur.execute("INSERT INTO notes (text) VALUES (?)", ("hello",))
con.commit()

rows = cur.execute("SELECT * FROM notes WHERE text LIKE ?", ("%hell%",)).fetchall()
for row in rows:
    print(row["text"])  # dict-like access with row_factory

# Integrity check
result = con.execute("PRAGMA integrity_check").fetchone()[0]
print("OK" if result == "ok" else f"CORRUPT: {result}")
con.close()
```

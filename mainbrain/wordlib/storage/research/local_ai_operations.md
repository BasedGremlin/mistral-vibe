# Local AI Operations: Complete Reference

## Ollama

### Essential Commands
```bash
ollama serve                          # Start server (default port 11434)
OLLAMA_HOST=0.0.0.0 ollama serve     # Expose to LAN
OLLAMA_MODELS=/path/to/models ollama serve  # Custom model dir (USB portability)
ollama list                           # Show downloaded models
ollama pull dolphin3:8b-llama3.1-q4_K_M    # Pull specific quantization
ollama rm model_name                  # Remove model
ollama show model_name                # Show model info + system prompt
ollama run dolphin3 "your prompt"     # Quick one-shot run
```

### API Endpoints (all POST unless noted)
```
GET  /api/tags              -- list models
POST /api/generate          -- raw completion
POST /api/chat              -- chat format (messages array)
POST /api/embeddings        -- get vector embeddings
POST /api/pull              -- pull a model
POST /api/delete            -- delete a model
GET  /api/version           -- server version
```

### Chat API Format
```json
{
  "model": "dolphin3:8b-llama3.1-q4_K_M",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain X"}
  ],
  "stream": false,
  "options": {
    "temperature": 0.7,
    "num_ctx": 4096,
    "top_p": 0.9
  }
}
```

### Quantization Guide
| Tag | Size | Quality | Use case |
|-----|------|---------|----------|
| Q2_K | ~2.5GB | Poor | Emergency, very low RAM |
| Q4_K_M | ~4.4GB | Good | **Best balance for USB** |
| Q5_K_M | ~5.0GB | Better | If USB space allows |
| Q8_0 | ~8GB | Near-lossless | Desktop only |
| F16 | ~16GB | Full | Workstation only |

### Useful Model Tags (verified June 2026)
```
dolphin3:8b-llama3.1-q4_K_M     -- 4.9GB, uncensored, general
qwen2.5-coder:7b-instruct-q4_K_M -- 4.7GB, coding, GDScript
nomic-embed-text                  -- 274MB, RAG embeddings
```

---

## LlamaIndex + ChromaDB (RAG stack)

### Index Build Pattern
```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
import chromadb

Settings.llm = Ollama(model="dolphin3", base_url="http://127.0.0.1:11434")
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
Settings.chunk_size = 512
Settings.chunk_overlap = 50

client = chromadb.PersistentClient(path="./storage/rag_index")
collection = client.get_or_create_collection("my_vault")
vector_store = ChromaVectorStore(chroma_collection=collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

docs = SimpleDirectoryReader(input_dir="./storage/kb", required_exts=[".md", ".txt"]).load_data()
index = VectorStoreIndex.from_documents(docs, storage_context=storage_context)
```

### Query Pattern
```python
engine = index.as_query_engine(similarity_top_k=5)
response = engine.query("how do I do X?")
for node in response.source_nodes:
    print(node.score, node.node.metadata.get("file_name"), node.node.text[:200])
```

### Troubleshooting RAG
- **Empty results**: Check that nomic-embed-text is pulled in Ollama
- **Slow indexing**: Normal on first run; subsequent runs use cached vectors
- **ChromaDB errors**: Delete rag_index/ folder to force full rebuild
- **Wrong chunks**: Adjust chunk_size (smaller = more precise, larger = more context)

---

## Flask + SQLAlchemy Patterns (ETHER AI reference)

### Model Definition
```python
class Note(db.Model):
    __tablename__ = "notes"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    content = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### Common Queries
```python
Note.query.count()
Note.query.order_by(Note.updated_at.desc()).limit(10).all()
Note.query.filter_by(category="research").all()
Note.query.filter(Note.title.contains("solar")).all()
db.session.add(Note(title="x", content="y"))
db.session.commit()
db.session.delete(note)
db.session.commit()
```

### JSON API Pattern
```python
@app.route("/api/notes", methods=["GET"])
def get_notes():
    notes = Note.query.order_by(Note.created_at.desc()).all()
    return jsonify([{"id": n.id, "title": n.title} for n in notes])
```

---

## Godot AI Plugin Integration

### Connecting Godot to Local Ollama (GDScript)
```gdscript
# HTTP request to local Ollama
func query_ai(prompt: String) -> void:
    var http = HTTPRequest.new()
    add_child(http)
    http.request_completed.connect(_on_response)
    
    var headers = ["Content-Type: application/json"]
    var body = JSON.stringify({
        "model": "qwen2.5-coder:7b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "stream": false
    })
    http.request("http://127.0.0.1:11434/api/chat", headers, HTTPClient.METHOD_POST, body)

func _on_response(result, code, headers, body):
    var response = JSON.parse_string(body.get_string_from_utf8())
    var text = response["message"]["content"]
    # use text
```

### Querying ETHER AI RAG from Godot
```gdscript
func query_rag(question: String) -> void:
    var http = HTTPRequest.new()
    add_child(http)
    http.request_completed.connect(_on_rag_response)
    
    var headers = ["Content-Type: application/json"]
    var body = JSON.stringify({"query": question, "top_k": 4})
    http.request("http://127.0.0.1:5757/api/rag/query", headers, HTTPClient.METHOD_POST, body)
```

---

## Performance Tuning

### Ollama on CPU
```bash
# More threads = faster, but check your CPU count
OLLAMA_NUM_PARALLEL=1 ollama serve   # One request at a time (good for USB)
# In modelfile or via API:
"options": {"num_thread": 8, "num_ctx": 2048}  # Lower ctx = faster
```

### RAG Chunk Size Guide
- **512 tokens** -- good for mixed content (default)
- **256 tokens** -- better recall, more chunks, slower
- **1024 tokens** -- better context, fewer chunks, may miss exact matches

### USB Speed Impact
- SanDisk Ultra Fit USB 3.0: ~130 MB/s read
- Loading a 4.9GB model from USB: ~38 seconds
- Solution: Use Ollama with OLLAMA_MODELS pointing to USB; model loads once then stays in RAM

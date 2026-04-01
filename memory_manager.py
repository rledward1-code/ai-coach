import json
import os
import math
import hashlib
from datetime import datetime
from openai import OpenAI

from history_manager import load_history, load_chat_log

MEMORY_STORE_FILE = "memory_store.json"
EMBEDDING_MODEL = "text-embedding-3-small"
MAX_CHAT_TURNS = 40
MAX_HISTORY_ITEMS = 20


def load_memory_store():
    if os.path.exists(MEMORY_STORE_FILE):
        try:
            with open(MEMORY_STORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("items", [])
        except Exception:
            return []
    return []


def save_memory_store(items):
    payload = {
        "version": 1,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "items": items,
    }
    with open(MEMORY_STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)


def _normalize_text(text):
    return " ".join(str(text).split())


def _build_id(prefix, text):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:16]}"


def _chunk_chat_turns(messages):
    turns = []
    current = []
    for msg in messages:
        if msg.get("role") == "user":
            if current:
                turns.append(current)
            current = [msg]
        else:
            current.append(msg)
    if current:
        turns.append(current)
    return turns[-MAX_CHAT_TURNS:]


def _build_memory_items():
    items = []

    history = load_history()
    for entry in history[-MAX_HISTORY_ITEMS:]:
        text = _normalize_text(entry.get("summary", ""))
        if not text:
            continue
        timestamp = entry.get("timestamp", "")
        item_id = _build_id("history", f"{timestamp}|{text}")
        items.append({
            "id": item_id,
            "type": "training_summary",
            "text": text,
            "metadata": {
                "timestamp": timestamp,
                "source": "coach_history",
                "title": f"跑步摘要 {timestamp}",
            },
        })

    chat_messages = load_chat_log()
    turns = _chunk_chat_turns(chat_messages)
    for idx, turn in enumerate(turns):
        lines = []
        timestamp = ""
        for msg in turn:
            role = msg.get("role", "")
            speaker = msg.get("name") if msg.get("name") else ("Edward" if role == "user" else role)
            lines.append(f"{speaker}: {msg.get('content', '')}")
            if not timestamp and msg.get("time"):
                timestamp = msg.get("time")
        text = _normalize_text("\n".join(lines))
        if not text:
            continue
        item_id = _build_id("chat", text)
        items.append({
            "id": item_id,
            "type": "chat_turn",
            "text": text,
            "metadata": {
                "timestamp": timestamp,
                "source": "chat_log",
                "title": f"對話回合 {idx + 1}",
            },
        })

    return items


def _embed_texts(api_key, texts):
    client = OpenAI(api_key=api_key.strip())
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    embeddings = []
    if hasattr(resp, "data"):
        for item in resp.data:
            embeddings.append(item.embedding)
    elif isinstance(resp, dict) and "data" in resp:
        for item in resp["data"]:
            embeddings.append(item["embedding"])
    return embeddings


def _cosine_similarity(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def sync_memory_store(api_key):
    try:
        canonical_items = _build_memory_items()
        existing = {item["id"]: item for item in load_memory_store()}
        updated_items = []
        to_embed = []
        embed_index = []

        for item in canonical_items:
            existing_item = existing.get(item["id"])
            if existing_item and existing_item.get("embedding"):
                item["embedding"] = existing_item["embedding"]
            else:
                to_embed.append(item["text"])
                embed_index.append(item)
            updated_items.append(item)

        if to_embed:
            embeddings = _embed_texts(api_key, to_embed)
            for item_obj, emb in zip(embed_index, embeddings):
                item_obj["embedding"] = emb

        save_memory_store(updated_items)
        return updated_items
    except Exception:
        return load_memory_store()


def get_relevant_memories(api_key, query, top_k=3):
    store = load_memory_store()
    if not store:
        return ""
    try:
        query_emb = _embed_texts(api_key, [query])[0]
    except Exception:
        return ""

    scored = []
    for item in store:
        emb = item.get("embedding")
        if not emb:
            continue
        score = _cosine_similarity(query_emb, emb)
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [item for score, item in scored[:top_k] if score > 0]
    if not selected:
        return ""

    lines = []
    for item in selected:
        text = item.get("text", "")
        if len(text) > 800:
            text = text[:800].strip() + "..."
        title = item.get("metadata", {}).get("title", "")
        lines.append(f"{title}\n{text}")
    return "\n\n".join(lines)

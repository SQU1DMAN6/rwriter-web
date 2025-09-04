import os
import json
import time
import requests
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

USERDATA_DIR = os.path.expanduser("~/RWRiter-userdata/")
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

app = FastAPI()

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Health check ---
@app.get("/healthz")
async def healthz():
    return {"ok": True}

# --- List chats ---
@app.get("/chats/{username}")
async def list_chats(username: str):
    user_dir = os.path.join(USERDATA_DIR, username)
    os.makedirs(user_dir, exist_ok=True)
    chats = [d for d in os.listdir(user_dir) if os.path.isdir(os.path.join(user_dir, d))]
    chats.sort()
    return {"chats": chats}

# --- Create new chat ---
@app.post("/chats/{username}/new")
async def new_chat(username: str):
    user_dir = os.path.join(USERDATA_DIR, username)
    os.makedirs(user_dir, exist_ok=True)
    chat_id = f"chat_{int(time.time() * 1000)}"
    chat_dir = os.path.join(user_dir, chat_id)
    os.makedirs(chat_dir)
    with open(os.path.join(chat_dir, "data.json"), "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)
    return {"chat_id": chat_id}

# --- Delete chat ---
@app.delete("/chats/{username}/{chatname}")
async def delete_chat(username: str, chatname: str):
    chat_dir = os.path.join(USERDATA_DIR, username, chatname)
    if not os.path.exists(chat_dir):
        return {"ok": False, "error": "Chat not found"}
    for root, dirs, files in os.walk(chat_dir, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(chat_dir)
    return {"ok": True}

# --- Load chat history ---
@app.get("/session/{username}/{chatname}")
async def get_session(username: str, chatname: str):
    chat_file = os.path.join(USERDATA_DIR, username, chatname, "data.json")
    if not os.path.exists(chat_file):
        return {"history": []}
    with open(chat_file, "r", encoding="utf-8") as f:
        history = json.load(f)
    return {"history": history}

# --- Simple search tool ---
def run_search(query: str):
    # Placeholder for demo
    return f"Search results for '{query}' (replace with real search API results)"

# --- Streaming chat endpoint ---
@app.post("/chat/{username}/{chatname}")
async def chat(username: str, chatname: str, request: Request):
    data = await request.json()
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return {"error": "No prompt provided"}

    chat_file = os.path.join(USERDATA_DIR, username, chatname, "data.json")
    os.makedirs(os.path.dirname(chat_file), exist_ok=True)

    # Load history
    history = []
    if os.path.exists(chat_file):
        with open(chat_file, "r", encoding="utf-8") as f:
            history = json.load(f)

    # Append user message
    history.append({"role": "user", "content": prompt})
    context_text = "\n".join([f"[{m['role'].upper()}] {m['content']}" for m in history])

    def event_stream():
        buffer = ""
        final_response = ""
        try:
            with requests.post(
                OLLAMA_URL,
                json={"model": "RWRiter:latest", "prompt": context_text, "stream": True},
                stream=True,
                timeout=600
            ) as ai_res:
                ai_res.raise_for_status()
                for chunk in ai_res.iter_content(chunk_size=64):
                    if chunk:
                        buffer += chunk.decode('utf-8')
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            try:
                                data_chunk = json.loads(line)
                                # Tool handling
                                if "action" in data_chunk:
                                    if data_chunk["action"] == "search":
                                        query = data_chunk.get("input", "")
                                        search_result = run_search(query)
                                        context_with_result = context_text + f"\n[SEARCH RESULTS]: {search_result}"
                                        # Re-query non-streaming
                                        followup = requests.post(
                                            OLLAMA_URL,
                                            json={"model": "RWRiter:latest", "prompt": context_with_result, "stream": True},
                                            stream=True,
                                            timeout=300
                                        )
                                        for fchunk in followup.iter_content(chunk_size=64):
                                            if fchunk:
                                                fbuf = fchunk.decode('utf-8')
                                                for fl in fbuf.split("\n"):
                                                    try:
                                                        fdata = json.loads(fl)
                                                        if "response" in fdata and fdata["response"]:
                                                            final_response += fdata["response"]
                                                            yield fdata["response"]
                                                    except:
                                                        continue
                                    elif data_chunk["action"] == "final" and "input" in data_chunk:
                                        final_response += data_chunk["input"]
                                        yield data_chunk["input"]
                                elif "response" in data_chunk and data_chunk["response"]:
                                    final_response += data_chunk["response"]
                                    yield data_chunk["response"]
                            except:
                                continue
        except Exception as e:
            yield f"⚠ Error: {e}"

        # Save final response
        history.append({"role": "bot", "content": final_response})
        with open(chat_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    return StreamingResponse(event_stream(), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)

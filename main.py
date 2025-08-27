import os
import json
import time
import requests
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

USERDATA_DIR = "/rwriter/userdata"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["quanthai.net"],
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

# --- Load chat history ---
@app.get("/session/{username}/{chatname}")
async def get_session(username: str, chatname: str):
    chat_file = os.path.join(USERDATA_DIR, username, chatname, "data.json")
    if not os.path.exists(chat_file):
        return {"history": []}
    with open(chat_file, "r", encoding="utf-8") as f:
        history = json.load(f)
    return {"history": history}

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

    # --- Streaming generator ---
    def event_stream():
        buffer = ""
        try:
            with requests.post(
                "http://127.0.0.1:11434/api/generate",
                json={"model": "SQU1DMAN/RWRiter:latest", "prompt": context_text, "stream": True},
                stream=True,
                timeout=300
            ) as ai_res:
                ai_res.raise_for_status()
                for chunk in ai_res.iter_content(chunk_size=64):
                    if chunk:
                        buffer += chunk.decode('utf-8')
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            try:
                                data = json.loads(line)
                                if "response" in data and data["response"]:
                                    yield data["response"]
                            except:
                                continue
        except Exception as e:
            yield f"⚠ Error: {e}"

        # Save full final response to history
        try:
            final_res = requests.post(
                "http://127.0.0.1:11434/api/generate",
                json={"model": "SQU1DMAN/RWRiter:latest", "prompt": context_text, "stream": False},
                timeout=300
            )
            final_text = final_res.json().get("response", "")
        except:
            final_text = "⚠ Could not save final response"

        history.append({"role": "bot", "content": final_text})
        with open(chat_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    return StreamingResponse(event_stream(), media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)

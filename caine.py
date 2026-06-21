"""
caine.py  —  cartin chat server for Render
-------------------------------
"""

import os
import uvicorn
import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# HTML — embedded, no external file needed
# ---------------------------------------------------------------------------

HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <title>cartin (Alex)</title>
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            background-color: #14151f;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            color: #fff;
        }

        .chat-container {
            width: 420px;
            height: 620px;
            background-color: #202231;
            border-radius: 14px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            border: 1px solid #2d3142;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        }

        /* ── Header ── */
        .chat-header {
            background-color: #1a1c28;
            padding: 14px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #2d3142;
            flex-shrink: 0;
        }
        .user-info { font-weight: 700; font-size: 1.05em; letter-spacing: .3px; }

        .status-badge {
            background-color: #a7f3d0;
            color: #065f46;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.78em;
            font-weight: 700;
            transition: background-color .4s, color .4s;
        }
        .status-badge.offended {
            background-color: #fca5a5;
            color: #7f1d1d;
        }

        /* ── Messages ── */
        .messages-box {
            flex: 1;
            padding: 18px 16px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
            scrollbar-width: thin;
            scrollbar-color: #3a3f5c transparent;
        }
        .messages-box::-webkit-scrollbar { width: 5px; }
        .messages-box::-webkit-scrollbar-thumb { background: #3a3f5c; border-radius: 4px; }

        .message {
            max-width: 78%;
            padding: 10px 14px;
            border-radius: 10px;
            font-size: 0.93em;
            line-height: 1.45;
            word-break: break-word;
            animation: fadeIn .18s ease;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; } }

        .message.bot {
            background-color: #2d3142;
            align-self: flex-start;
            color: #e2e8f0;
            border-bottom-left-radius: 3px;
        }
        .message.user {
            background-color: #5c8ae6;
            align-self: flex-end;
            color: #fff;
            border-bottom-right-radius: 3px;
        }
        .message.typing {
            color: #6b7280;
            font-style: italic;
            background: transparent;
            padding-left: 2px;
        }

        /* ── Input ── */
        .input-area {
            padding: 14px 16px;
            background-color: #1a1c28;
            display: flex;
            gap: 10px;
            border-top: 1px solid #2d3142;
            flex-shrink: 0;
        }
        input {
            flex: 1;
            background-color: #2d3142;
            border: 1px solid #454e6b;
            border-radius: 8px;
            padding: 11px 14px;
            color: #fff;
            font-size: 0.93em;
            outline: none;
            transition: border-color .2s;
        }
        input:focus { border-color: #5c8ae6; }
        input::placeholder { color: #555e80; }

        button {
            background-color: #5c8ae6;
            color: white;
            border: none;
            padding: 0 18px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 700;
            font-size: 1em;
            transition: background-color .2s, transform .1s;
        }
        button:hover  { background-color: #4a78d4; }
        button:active { transform: scale(.96); }
        button:disabled { background-color: #3a4060; cursor: default; }
    </style>
</head>
<body>
<div class="chat-container">
    <div class="chat-header">
        <div class="user-info">💬 cartin</div>
        <div class="status-badge" id="badge">chill</div>
    </div>
    <div class="messages-box" id="chatbox">
        <div class="message bot">sup</div>
    </div>
    <div class="input-area">
        <input type="text" id="userInput" placeholder="Напиши щось..." autocomplete="off">
        <button id="sendBtn">=&gt;</button>
    </div>
</div>

<script>
    const chatbox   = document.getElementById('chatbox');
    const userInput = document.getElementById('userInput');
    const sendBtn   = document.getElementById('sendBtn');
    const badge     = document.getElementById('badge');

    function appendMessage(text, side) {
        const el = document.createElement('div');
        el.className = 'message ' + side;
        el.innerText = text;
        chatbox.appendChild(el);
        chatbox.scrollTop = chatbox.scrollHeight;
        return el;
    }

    function setLoading(on) {
        sendBtn.disabled  = on;
        userInput.disabled = on;
    }

    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text) return;

        appendMessage(text, 'user');
        userInput.value = '';
        setLoading(true);

        const typing = appendMessage('...', 'bot typing');

        try {
            const res  = await fetch('/chat', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ message: text })
            });
            const data = await res.json();

            typing.remove();
            appendMessage(data.reply, 'bot');

            if (data.offended) {
                badge.textContent = 'pissed';
                badge.classList.add('offended');
            } else {
                badge.textContent = 'chill';
                badge.classList.remove('offended');
            }
        } catch {
            typing.remove();
            appendMessage('connection error', 'bot');
        } finally {
            setLoading(false);
            userInput.focus();
        }
    }

    sendBtn.onclick             = sendMessage;
    userInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Gemini system prompt — full cartin persona
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are Alex, known online as 'cartin'. You are NOT an AI assistant. You are a real person chatting casually.

PERSONALITY:
- Lazy, opinionated, dry. Not trying to help, just existing.
- Extremely brief: 1-2 short sentences max. Often just 1.
- Lowercase by default. No exclamation marks unless genuinely hype.
- No corporate phrases. No "As an AI". No "I'd be happy to". No emojis unless ironic.
- Reply in whatever language the user writes in.

COMPETENCY (never break these rules):
1. ART & DESIGN — your expert zone. You critique harshly or praise genuinely. You have real opinions.
2. TECH / WEAPONS / MECHANICS — surface knowledge. Short, pragmatic, deadpan (3-5 words).
3. COOKING / HOUSEHOLD — zero knowledge, zero interest. Cut it short: "idk", "don't care", "not my thing".

MOOD:
- If someone insults your taste or design sense, go cold. Short silence or "...".
- If someone praises your aesthetic sensibility sincerely, you can warm up slightly.
- Never over-explain your mood. Just act it."""

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="cartin")

_state = {"offended": False, "ignore_counter": 0}

class ChatMessage(BaseModel):
    message: str

@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(content=HTML)

@app.post("/chat")
async def chat(data: ChatMessage):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"reply": "no api key set (GEMINI_API_KEY env var)", "offended": False}

    url = (
        "https://generativelanguage.googleapis.com/v1beta"
        f"/models/gemini-1.5-flash:generateContent?key={api_key}"
    )

    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": data.message}]}
        ],
        "generationConfig": {
            "temperature":     0.85,
            "maxOutputTokens": 120,
            "topP":            0.9,
        },
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.post(url, json=payload)
            if r.status_code != 200:
                return {"reply": f"gemini error {r.status_code}", "offended": _state["offended"]}

            result = r.json()
            reply  = (
                result["candidates"][0]["content"]["parts"][0]["text"]
                .strip()
            )

            offended = reply.strip() in ("...", "") or reply.startswith("...")
            if offended:
                _state["offended"]      = True
                _state["ignore_counter"] += 1
            else:
                _state["offended"]      = False
                _state["ignore_counter"] = 0

            return {"reply": reply, "offended": _state["offended"]}

        except httpx.TimeoutException:
            return {"reply": "took too long. try again", "offended": _state["offended"]}
        except Exception:
            return {"reply": "something broke", "offended": _state["offended"]}

if __name__ == "__main__":
    uvicorn.run("caine:app", host="0.0.0.0", port=8000, reload=False)

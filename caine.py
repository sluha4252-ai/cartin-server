import os
import codecs
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx

app = FastAPI()

class ChatMessage(BaseModel):
    message: str

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Чистий HTML-текст, переведений у байтовий формат, щоб уникнути конфліктів синтаксису Python/JS
RAW_HTML = codecs.encode("""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <title>cartin (Alex)</title>
    <style>
        body { background-color: #14151f; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; color: #fff; }
        .chat-container { width: 400px; height: 600px; background-color: #202231; border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; border: 1px solid #2d3142; }
        .chat-header { background-color: #1a1c28; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2d3142; }
        .user-info { font-weight: bold; font-size: 1.1em; }
        .status-badge { background-color: #a7f3d0; color: #065f46; padding: 4px 12px; border-radius: 20px; font-size: 0.8em; font-weight: 600; }
        .messages-box { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; }
        .message { max-width: 75%; padding: 12px 16px; border-radius: 8px; font-size: 0.95em; }
        .message.bot { background-color: #2d3142; align-self: flex-start; color: #e2e8f0; }
        .message.user { background-color: #5c8ae6; align-self: flex-end; color: #fff; }
        .input-area { padding: 15px; background-color: #1a1c28; display: flex; gap: 10px; border-top: 1px solid #2d3142; }
        input { flex: 1; background-color: #2d3142; border: 1px solid #454e6b; border-radius: 6px; padding: 12px; color: #fff; outline: none; }
        button { background-color: #5c8ae6; color: white; border: none; padding: 0 20px; border-radius: 6px; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <div class="user-info">💬 cartin (Alex)</div>
            <div class="status-badge">chill</div>
        </div>
        <div class="messages-box" id="chatbox">
            <div class="message bot">sup</div>
        </div>
        <div class="input-area">
            <input type="text" id="userInput" placeholder="Напиши щось Алексу...">
            <button id="sendBtn">==&gt;</button>
        </div>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const chatbox = document.getElementById('chatbox');
            const userInput = document.getElementById('userInput');
            const sendBtn = document.getElementById('sendBtn');

            function appendMessage(text, side) {
                const msg = document.createElement('div');
                msg.classList.add('message', side);
                msg.innerText = text;
                chatbox.appendChild(msg);
                chatbox.scrollTop = chatbox.scrollHeight;
            }

            async function sendMessage() {
                const text = userInput.value.trim();
                if (!text) return;
                
                appendMessage(text, 'user');
                userInput.value = '';
                
                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: text })
                    });
                    const data = await response.json();
                    appendMessage(data.reply, 'bot');
                } catch (err) {
                    appendMessage('Помилка з\'єднання з сервером.', 'bot');
                }
            }

            if (sendBtn) {
                sendBtn.onclick = sendMessage;
            }
            if (userInput) {
                userInput.onkeypress = function(e) {
                    if (e.key === 'Enter') {
                        sendMessage();
                    }
                };
            }
        });
    </script>
</body>
</html>""", "utf-8")

@app.get("/", response_class=HTMLResponse)
def read_root():
    return RAW_HTML.decode("utf-8")

@app.post("/chat")
async def chat_with_gemini(data: ChatMessage):
    if not GEMINI_API_KEY:
        return {"reply": "Помилка: На сервері не налаштовано GEMINI_API_KEY!"}
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": data.message}]}],
        "systemInstruction": {
            "parts": [{"text": "Ти — хлопець на ім'я Алекс (нік cartin). Твій стиль спілкування — максимально розслаблений (chill), дружній, пофігістичний. Відповідай коротко, використовуй сленг. Спілкуйся тією мовою, якою до тебе звертаються."}]
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=20.0)
            if response.status_code == 200:
                result = response.json()
                return {"reply": result['candidates'][0]['content']['parts'][0]['text'].strip()}
            return {"reply": f"Бот задумався... Код: {response.status_code}"}
        except Exception:
            return {"reply": "Алекс кудись відійшов."}

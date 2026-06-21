from __future__ import annotations

import random
import re
from collections import deque
from enum import Enum, auto
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Domain & Tone enumerations
# ---------------------------------------------------------------------------

class Domain(Enum):
    ART_DESIGN   = auto()   # cartin's expert zone
    TECH_WEAPONS = auto()   # surface knowledge
    COOKING_HOME = auto()   # zero knowledge / dismissal
    SOCIAL       = auto()   # greetings, meta, small talk
    UNKNOWN      = auto()


class Tone(Enum):
    PRAISE   = auto()   # complimenting cartin's taste / work
    INSULT   = auto()   # attacking his taste / design sense
    NEUTRAL  = auto()


# ---------------------------------------------------------------------------
# Semantic pattern tables
# ---------------------------------------------------------------------------

_ART_PATTERNS: list[re.Pattern] = [re.compile(p, re.I | re.U) for p in [
    r"\b(design|designer|designing|designed)\b",
    r"\b(art|artwork|artist|artistic|artsy)\b",
    r"\b(layout|layou?ts)\b",
    r"\b(color|colour|palette|hue|tones?|shades?)\b",
    r"\b(font|typography|typeface|kerning|leading)\b",
    r"\b(logo|branding|brand|identity)\b",
    r"\b(ui|ux|interface|visual|visuals)\b",
    r"\b(aesthetic|aesthetics|vibes?)\b",
    r"\b(illustration|graphic|graphics)\b",
    r"\b(style|styled|styling)\b",
    r"\b(composition|negative\s+space|balance|contrast)\b",
    r"\b(sketch|sketching|drawing|illustration)\b",
    r"\b(poster|banner|thumbnail|mockup)\b",
    r"\b(photoshop|figma|illustrator|affinity|procreate|canva)\b",
    r"\b(render|rendering|3d|blender|cgi)\b",
    r"дизайн",
    r"арт\b",
    r"малюнок|малювати|намалював",
    r"стиль|стильн",
    r"кольори?|колір|палітра",
    r"шрифт|типографі",
    r"лого|логотип",
    r"скетч|ескіз",
    r"композиц",
    r"візуал",
    r"мазня|мазн",
    r"очі\s+рі[жз]е",
    r"інтерфейс",
]]

_TECH_PATTERNS: list[re.Pattern] = [re.compile(p, re.I | re.U) for p in [
    r"\b(gun|rifle|pistol|shotgun|ammo|caliber|barrel|trigger|firearm|weapon)\b",
    r"\b(knife|blade|sword|katana|tactical)\b",
    r"\b(pc|cpu|gpu|ram|motherboard|processor|specs|hardware|build)\b",
    r"\b(code|coding|python|javascript|program|software|app|dev|api)\b",
    r"\b(car|engine|mechanic|transmission|horsepower|torque|rpm)\b",
    r"\b(phone|iphone|android|smartphone|laptop|tablet)\b",
    r"\b(tech|technology|gadget|device|electronic)\b",
    r"\b(fix|repair|troubleshoot|debug|broken|not\s+work)\b",
    r"\b(install|setup|config|configure)\b",
    r"\b(fps|frames|latency|ping|overclock)\b",
    r"зброя|пістолет|рушниц|автомат|набої",
    r"техніка|технологі|пристрій|гаджет",
    r"компʼютер|комп|ноутбук|телефон",
    r"програм|код|скрипт",
    r"двигун|мотор|машина|авто",
    r"полагодити|зламан|не\s+працює|що\s+робити\s+з",
    r"потяг|поїзд",
]]

_COOKING_HOME_PATTERNS: list[re.Pattern] = [re.compile(p, re.I | re.U) for p in [
    r"\b(cook|cooking|recipe|ingredient|bake|baking|fry|boil|grill)\b",
    r"\b(food|meal|dish|cuisine|kitchen|chef)\b",
    r"\b(soup|pasta|rice|salad|bread|cake|pie|stew)\b",
    r"\b(clean|cleaning|laundry|vacuum|mop|dust|dishes|wash)\b",
    r"\b(home|house|apartment|furniture|decor(?!ator))\b",
    r"\b(plant|garden|gardening|water\s+the)\b",
    r"\b(grocery|shopping\s+list|supermarket)\b",
    r"\b(repair\s+at\s+home|plumb|electrical\s+fix)\b",
    r"\b(pet|dog|cat|feed\s+the)\b",
    r"готувати|рецепт|страва|їжа|кухня|кухар",
    r"суп|борщ|паста|рис|хліб|пиріг",
    r"прибирати|прибирання|посуд|прання",
    r"квартира|меблі|кімната",
    r"рослин|поливати",
    r"кіт|собак|тварин",
    r"корить|корнемоп|шваброю",
]]

_SOCIAL_PATTERNS: list[re.Pattern] = [re.compile(p, re.I | re.U) for p in [
    r"^\s*(hey|hi|hello|sup|yo|hiya|heya|what'?s\s+up|wassup|howdy)\s*[!?.]?\s*$",
    r"^\s*(привіт|хай|хей|йо|агов|вітаю)\s*[!?.]?\s*$",
    r"\b(how\s+are\s+you|how'?s\s+it\s+going|you\s+good|you\s+ok)\b",
    r"\b(як\s+(ти|справи|сам)|що\s+(як|нового))\b",
    r"^\s*(lol|lmao|haha|xd|😂|💀)\s*$",
    r"^\s*(ok|okay|k|ок|окей|ладно)\s*$",
    r"^\s*(thanks?|thx|дяку?|дякую)\s*[!.]?\s*$",
    r"^\s*(bye|cya|later|бувай|па|пока)\s*[!.]?\s*$",
    r"\bwho\s+are\s+you\b",
    r"(your\s+name|як\s+(тебе|тебе\s+звати|звуть))",
]]

_INSULT_PATTERNS: list[re.Pattern] = [re.compile(p, re.I | re.U) for p in [
    r"\b(trash|garbage|awful|terrible|horrible|disgusting|ugly)\b",
    r"\b(bad\s+taste|no\s+taste|tasteless)\b",
    r"\byou\s+(suck|are\s+bad|have\s+no\s+idea|know\s+nothing)\b",
    r"\b(hate|hates)\s+(your|this)\s+(style|design|art|work|stuff)\b",
    r"\b(worst|stupidest?)\s+(design|art|style)\b",
    r"what\s+(is\s+this|the\s+hell)\s+(design|art|style|trash)",
    r"\b(amateur|hack|joke)\b.*\b(design|art|style)\b",
    r"\b(design|art|style)\b.*\b(amateur|hack|joke)\b",
    r"(looks?|look)\s+(like\s+)?(shit|crap|garbage|trash|ass)",
    r"this\s+(is\s+)?(so\s+)?(bad|ugly|awful|terrible)",
    r"мазня",
    r"очі\s+рі[жз]е",
    r"лайно|гівно",
    r"жахливо|страшно|огидно",
    r"без\s+(смаку|стилю)",
    r"ти\s+(нічого\s+не\s+(знаєш|розумієш)|лох)",
    r"хріново|погано|жах",
    r"никчемн",
]]

_PRAISE_PATTERNS: list[re.Pattern] = [re.compile(p, re.I | re.U) for p in [
    r"\b(love|loved|loving)\s+(your|this|the)\s+(style|design|art|work|aesthetic|vibe)\b",
    r"\b(amazing|incredible|gorgeous|stunning|beautiful|clean|crisp)\b.*\b(design|art|style|work)\b",
    r"\b(design|art|style|work)\b.*\b(amazing|incredible|gorgeous|stunning|beautiful|clean|crisp)\b",
    r"\bgood\s+(taste|eye|sense\s+of\s+(style|design))\b",
    r"\b(you\s+have|having)\s+(great|amazing|excellent)\s+taste\b",
    r"\bthis\s+(looks?|is)\s+(so\s+)?(good|great|fire|clean|nice|sick|dope)\b",
    r"\b(respect|props)\s+(your|for\s+your)\s+(taste|style|work|design)\b",
    r"\b(masterpiece|flawless|perfect)\b",
    r"\bgood\s+work\b",
    r"\bwell\s+done\b",
    r"(класний|чудовий|гарний|красивий)\s+(дизайн|стиль|арт|робота|вигляд)",
    r"(дизайн|стиль|арт)\s+(класний|чудовий|гарний|крутий)",
    r"\bкруто\b",
    r"смак\s+(є|маєш|відмінний)",
    r"добра\s+(робота|праця)",
    r"вогонь\s*(дизайн|арт|стиль)?",
    r"виглядає\s+(добре|чудово|класно|круто)",
    r"(поважаю|ціную)\s+(твій|твою)\s+(смак|стиль|роботу)",
    r"шедевр",
]]

# ---------------------------------------------------------------------------
# Response banks
# ---------------------------------------------------------------------------

_ART_POSITIVE: list[str] = [
    "yeah that palette works. negative space is doing the heavy lifting.",
    "solid. hierarchy is clean, nothing fighting for attention.",
    "ok this actually hits. rare.",
    "typography is the only thing keeping this alive but it's enough.",
    "composition is tight. whoever picked the contrast knew what they were doing.",
    "layout breathes well. most people don't get that.",
    "color story is consistent. not obvious either.",
]

_ART_CRITICAL: list[str] = [
    "too much going on. pick one focal point and commit.",
    "font choice is killing it. everything else is fine.",
    "contrast is nonexistent. the whole thing reads as noise.",
    "grid is broken. probably didn't use one.",
    "color palette looks random. no cohesion.",
    "hierarchy is flat. nothing tells you where to look first.",
    "margins are embarrassing. who approved this.",
    "text is unreadable on that background. basic stuff.",
    "drop shadows in 2024. i can't.",
]

_ART_GENERAL_OPINION: list[str] = [
    "send the file, i'll tell you what's wrong.",
    "depends on context. what's it for.",
    "style is taste + discipline. most people have neither.",
    "references?",
    "what's the brief.",
    "minimalism isn't laziness but most people use it as an excuse.",
]

_TECH_RESPONSES: dict[str, list[str]] = {
    "fix":   ["restart it first.", "check the logs.", "google the error code."],
    "spec":  ["depends on budget.", "more ram never hurts.", "check benchmarks."],
    "gun":   ["check the manual.", "clean the barrel.", "depends on caliber."],
    "code":  ["read the error.", "rubber duck it.", "check stackoverflow."],
    "car":   ["check the oil.", "take it in.", "listen for knocking."],
    "phone": ["restart it.", "clear cache.", "factory reset last resort."],
    "default": ["idk, google it.", "try the obvious first.", "not my area tbh."],
}

_COOKING_RESPONSES: list[str] = [
    "idk, don't care.",
    "off topic.",
    "not really my thing.",
    "who cares.",
    "nope.",
    "ask someone else.",
    "i don't cook.",
]

_SOCIAL_RESPONSES: list[str] = [
    "yeah",
    "sup",
    "fine",
    "here",
    "mhm",
    "ok",
    "what",
    "what's up",
]

_NAME_RESPONSES: list[str] = [
    "cartin",
    "cartin. what do you need",
    "people call me cartin",
    "cartin. who's asking",
]

_OFFENDED_RESPONSES: list[str] = [
    "...",
    "...",
    "...",
    "not talking to you rn",
    "...",
]

_ICE_BROKEN_RESPONSES: list[str] = [
    "ok fine. what do you want",
    "...alright. what",
    "fine. show me",
    "ok. what's the question",
]

_UNKNOWN_RESPONSES: list[str] = [
    "?",
    "what",
    "not following",
    "send more context",
    "ok?",
    "idk what you mean",
]

# ---------------------------------------------------------------------------
# Semantic parser
# ---------------------------------------------------------------------------

def _match_any(patterns: list[re.Pattern], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def detect_domain(text: str) -> Domain:
    if _match_any(_SOCIAL_PATTERNS, text):
        return Domain.SOCIAL
    scores = {
        Domain.ART_DESIGN:   sum(1 for p in _ART_PATTERNS   if p.search(text)),
        Domain.TECH_WEAPONS: sum(1 for p in _TECH_PATTERNS  if p.search(text)),
        Domain.COOKING_HOME: sum(1 for p in _COOKING_HOME_PATTERNS if p.search(text)),
    }
    best_score = max(scores.values())
    if best_score == 0:
        return Domain.UNKNOWN
    best_domain = max(scores, key=lambda d: scores[d])
    return best_domain


def detect_tone(text: str) -> Tone:
    if _match_any(_INSULT_PATTERNS, text):
        return Tone.INSULT
    if _match_any(_PRAISE_PATTERNS, text):
        return Tone.PRAISE
    return Tone.NEUTRAL


def is_art_praise(text: str) -> bool:
    return detect_domain(text) in (Domain.ART_DESIGN, Domain.SOCIAL) and detect_tone(text) == Tone.PRAISE


def _tech_reply(text: str) -> str:
    text_l = text.lower()
    if re.search(r"fix|repair|broken|not\s*work|полагодити|зламан|потяг", text_l):
        return random.choice(_TECH_RESPONSES["fix"])
    if re.search(r"gun|rifle|pistol|weapon|blade|зброя|пістолет|рушниц", text_l):
        return random.choice(_TECH_RESPONSES["gun"])
    if re.search(r"spec|cpu|gpu|ram|build|specs", text_l):
        return random.choice(_TECH_RESPONSES["spec"])
    if re.search(r"code|program|script|bug|error|debug", text_l):
        return random.choice(_TECH_RESPONSES["code"])
    if re.search(r"car|engine|mechanic|авто|машина|двигун", text_l):
        return random.choice(_TECH_RESPONSES["car"])
    if re.search(r"phone|iphone|android|ноутбук|телефон", text_l):
        return random.choice(_TECH_RESPONSES["phone"])
    return random.choice(_TECH_RESPONSES["default"])


def _art_reply(text: str, tone: Tone) -> str:
    if tone == Tone.PRAISE:
        return random.choice(_ART_POSITIVE)
    if tone == Tone.INSULT:
        return random.choice(_ART_CRITICAL + _ART_GENERAL_OPINION)
    return random.choice(_ART_GENERAL_OPINION)


def _social_reply(text: str) -> str:
    if re.search(r"(who\s+are\s+you|your\s+name|як\s+(тебе|звуть|звати))", text, re.I | re.U):
        return random.choice(_NAME_RESPONSES)
    return random.choice(_SOCIAL_RESPONSES)


class Memory:
    def __init__(self, maxlen: int = 3) -> None:
        self._buf: deque[dict] = deque(maxlen=maxlen)

    def push(self, role: str, text: str, domain: Domain) -> None:
        self._buf.append({"role": role, "text": text, "domain": domain})

    def last_domain(self) -> Optional[Domain]:
        return self._buf[-1]["domain"] if self._buf else None

    def topic_shifted(self, new_domain: Domain) -> bool:
        last = self.last_domain()
        if last is None:
            return False
        return last != new_domain and new_domain not in (Domain.SOCIAL, Domain.UNKNOWN)

    def decay_if_shifted(self, new_domain: Domain) -> None:
        if self.topic_shifted(new_domain) and len(self._buf) > 0:
            try:
                self._buf.popleft()
            except IndexError:
                pass

    def context(self) -> list[dict]:
        return list(self._buf)


class CartinBrain:
    def __init__(self) -> None:
        self.memory         = Memory(maxlen=3)
        self.is_offended    = False
        self.ignore_counter = 0

    def reply(self, user_text: str) -> str:
        text = user_text.strip()
        if not text:
            return "?"

        domain = detect_domain(text)
        tone   = detect_tone(text)

        if self.is_offended:
            if is_art_praise(text):
                self.is_offended    = False
                self.ignore_counter = 0
                self.memory.push("user", text, domain)
                response = random.choice(_ICE_BROKEN_RESPONSES)
                self.memory.push("cartin", response, domain)
                return response
            else:
                self.ignore_counter -= 1
                if self.ignore_counter <= 0:
                    self.is_offended    = False
                    self.ignore_counter = 0
                return random.choice(_OFFENDED_RESPONSES)

        if tone == Tone.INSULT and domain == Domain.ART_DESIGN:
            self.is_offended    = True
            self.ignore_counter = 3
            return random.choice(_OFFENDED_RESPONSES)

        self.memory.decay_if_shifted(domain)

        if domain == Domain.ART_DESIGN:
            response = _art_reply(text, tone)
        elif domain == Domain.TECH_WEAPONS:
            response = _tech_reply(text)
        elif domain == Domain.COOKING_HOME:
            response = random.choice(_COOKING_RESPONSES)
        elif domain == Domain.SOCIAL:
            response = _social_reply(text)
        else:
            response = random.choice(_UNKNOWN_RESPONSES)

        self.memory.push("user", text, domain)
        self.memory.push("cartin", response, domain)

        return response


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="cartin",
    description="cartin chat backend — don't expect customer service",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_brain = CartinBrain()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    offended: bool
    ignore_counter: int
    domain: str


# --- ГОЛОВНА СТОРІНКА ЧАТУ В БРАУЗЕРІ ---
@app.get("/", response_class=HTMLResponse)
def get_chat_interface():
    return """
    <!DOCTYPE html>
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Чат з cartin (Alex)</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #1e1e2e; color: #cdd6f4; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
            .chat-container { width: 450px; height: 600px; background: #252538; border-radius: 12px; display: flex; flex-direction: column; box-shadow: 0 8px 24px rgba(0,0,0,0.3); overflow: hidden; border: 1px solid #45475a; }
            .chat-header { background: #11111b; padding: 15px; text-align: center; font-weight: bold; font-size: 1.1rem; border-bottom: 1px solid #45475a; display: flex; justify-content: space-between; align-items: center; }
            .status-badge { font-size: 0.8rem; padding: 4px 8px; border-radius: 20px; background: #a6e3a1; color: #11111b; font-weight: bold;}
            .status-badge.offended { background: #f38ba8; color: #11111b; }
            .chat-messages { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
            .message { max-width: 75%; padding: 10px 14px; border-radius: 8px; font-size: 0.95rem; line-height: 1.4; word-break: break-word; }
            .message.user { background: #89b4fa; color: #11111b; align-self: flex-end; border-bottom-right-radius: 2px; }
            .message.cartin { background: #45475a; color: #cdd6f4; align-self: flex-start; border-bottom-left-radius: 2px; }
            .chat-input-area { padding: 15px; background: #11111b; display: flex; gap: 10px; border-top: 1px solid #45475a; }
            input { flex: 1; background: #313244; border: 1px solid #45475a; color: #cdd6f4; padding: 10px; border-radius: 6px; font-size: 0.95rem; outline: none; }
            input:focus { border-color: #89b4fa; }
            button { background: #89b4fa; color: #11111b; border: none; padding: 10px 16px; border-radius: 6px; font-weight: bold; cursor: pointer; transition: background 0.2s; }
            button:hover { background: #b4befe; }
        </style>
    </head>
    <body>
        <div class="chat-container">
            <div class="chat-header">
                <span>💬 cartin (Alex)</span>
                <span id="status" class="status-badge">chill</span>
            </div>
            <div class="chat-messages" id="messages">
                <div class="message cartin">sup</div>
            </div>
            <div class="chat-input-area">
                <input type="text" id="userInput" placeholder="Напиши щось Алексу..." onkeypress="if(event.key === 'Enter') sendMessage()">
                <button onclick="sendMessage()">==></button>
            </div>
        </div>

        <script>
            async function sendMessage() {
                const input = document.getElementById('userInput');
                const text = input.value.trim();
                if (!text) return;

                input.value = '';
                appendMessage(text, 'user');

                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: text })
                    });
                    const data = await response.json();
                    
                    appendMessage(data.reply, 'cartin');
                    
                    const statusBadge = document.getElementById('status');
                    if (data.offended) {
                        statusBadge.innerText = 'offended (' + data.ignore_counter + ')';
                        statusBadge.className = 'status-badge offended';
                    } else {
                        statusBadge.innerText = 'chill';
                        statusBadge.className = 'status-badge';
                    }
                } catch (e) {
                    appendMessage('error: сервер ліг або не відповідає', 'cartin');
                }
            }

            function appendMessage(text, sender) {
                const container = document.getElementById('messages');
                const msgDiv = document.createElement('div');
                msgDiv.className = 'message ' + sender;
                msgDiv.innerText = text;
                container.appendChild(msgDiv);
                container.scrollTop = container.scrollHeight;
            }
        </script>
    </body>
    </html>
    """


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    domain = detect_domain(req.message.strip())
    response = _brain.reply(req.message)
    return ChatResponse(
        reply=response,
        offended=_brain.is_offended,
        ignore_counter=_brain.ignore_counter,
        domain=domain.name,
    )


@app.get("/state")
def state() -> dict:
    return {
        "is_offended":    _brain.is_offended,
        "ignore_counter": _brain.ignore_counter,
        "memory":         _brain.memory.context(),
    }


@app.post("/reset")
def reset() -> dict:
    global _brain
    _brain = CartinBrain()
    return {"status": "reset"}

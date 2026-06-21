"""
cartin_server.py
----------------
Self-contained FastAPI chat server for the 'cartin' (Alex) persona.
No external LLM APIs required. Runs out-of-the-box.

Install:
    pip install fastapi uvicorn

Run:
    python cartin_server.py

Endpoint:
    POST http://localhost:8000/chat
    Body: { "message": "your message here" }
"""

from __future__ import annotations

import random
import re
from collections import deque
from enum import Enum, auto
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
# Each pattern: (compiled_regex, Domain)  |  (compiled_regex, Tone)
# Patterns are intentionally broad to catch conversational variations,
# typos, Ukrainian/Russian/English code-switching, slang.
# ---------------------------------------------------------------------------

_ART_PATTERNS: list[re.Pattern] = [re.compile(p, re.I | re.U) for p in [
    # English
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
    # Ukrainian / Russian transliterated / Cyrillic
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
    r"мазня|мазн",          # "daub / bad painting" — could be insult referencing art
    r"очі\s+рі[жз]е",       # "eyes bleed" — art insult phrase
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
    # Ukrainian
    r"зброя|пістолет|рушниц|автомат|набої",
    r"техніка|технологі|пристрій|гаджет",
    r"компʼютер|комп|ноутбук|телефон",
    r"програм|код|скрипт",
    r"двигун|мотор|машина|авто",
    r"полагодити|зламан|не\s+працює|що\s+робити\s+з",
    r"потяг|поїзд",          # train — maintenance/tech
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
    # Ukrainian
    r"готувати|рецепт|страва|їжа|кухня|кухар",
    r"суп|борщ|паста|рис|хліб|пиріг",
    r"прибирати|прибирання|посуд|прання",
    r"квартира|меблі|кімната",
    r"рослин|поливати",
    r"кіт|собак|тварин",
    r"корить|корнемоп|шваброю",   # mop/household cleaning items
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

# ---- Tone patterns -------------------------------------------------------

_INSULT_PATTERNS: list[re.Pattern] = [re.compile(p, re.I | re.U) for p in [
    # English — attacking taste / design
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
    # Ukrainian / transliterated
    r"мазня",                           # "daub" as insult
    r"очі\s+рі[жз]е",                  # "eyes bleed"
    r"лайно|гівно",                     # "shit"
    r"жахливо|страшно|огидно",          # "awful/terrible/disgusting"
    r"без\s+(смаку|стилю)",             # "tasteless"
    r"ти\s+(нічого\s+не\s+(знаєш|розумієш)|лох)",
    r"хріново|погано|жах",
    r"нікчемн",                          # worthless
]]

_PRAISE_PATTERNS: list[re.Pattern] = [re.compile(p, re.I | re.U) for p in [
    # English
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
    # Ukrainian
    r"(класний|чудовий|гарний|красивий)\s+(дизайн|стиль|арт|робота|вигляд)",
    r"(дизайн|стиль|арт)\s+(класний|чудовий|гарний|крутий)",
    r"\bкруто\b",
    r"смак\s+(є|маєш|відмінний)",
    r"добра\s+(робота|праця)",
    r"вогонь\s*(дизайн|арт|стиль)?",    # "fire design"
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
# Semantic parser — pure Python, no external deps
# ---------------------------------------------------------------------------

def _match_any(patterns: list[re.Pattern], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def detect_domain(text: str) -> Domain:
    # Social check first (short greetings/reactions take priority)
    if _match_any(_SOCIAL_PATTERNS, text):
        return Domain.SOCIAL
    # Score each domain by pattern hit count (richer matching wins ties)
    scores = {
        Domain.ART_DESIGN:   sum(1 for p in _ART_PATTERNS        if p.search(text)),
        Domain.TECH_WEAPONS: sum(1 for p in _TECH_PATTERNS        if p.search(text)),
        Domain.COOKING_HOME: sum(1 for p in _COOKING_HOME_PATTERNS if p.search(text)),
    }
    best_score = max(scores.values())
    if best_score == 0:
        return Domain.UNKNOWN
    best_domain = max(scores, key=lambda d: scores[d])
    return best_domain


def detect_tone(text: str) -> Tone:
    # Insult check before praise — insults can contain design references
    if _match_any(_INSULT_PATTERNS, text):
        return Tone.INSULT
    if _match_any(_PRAISE_PATTERNS, text):
        return Tone.PRAISE
    return Tone.NEUTRAL


def is_art_praise(text: str) -> bool:
    """Ice-breaker condition: design domain AND praise tone."""
    return detect_domain(text) in (Domain.ART_DESIGN, Domain.SOCIAL) and detect_tone(text) == Tone.PRAISE


# ---------------------------------------------------------------------------
# Tech response selector — picks a sub-category reply
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Art response selector
# ---------------------------------------------------------------------------

def _art_reply(text: str, tone: Tone) -> str:
    if tone == Tone.PRAISE:
        return random.choice(_ART_POSITIVE)
    if tone == Tone.INSULT:
        # Insult about someone else's art (not directed at cartin personally)
        # — cartin can agree or give an opinion
        return random.choice(_ART_CRITICAL + _ART_GENERAL_OPINION)
    return random.choice(_ART_GENERAL_OPINION)


# ---------------------------------------------------------------------------
# Social / name response
# ---------------------------------------------------------------------------

def _social_reply(text: str) -> str:
    if re.search(r"(who\s+are\s+you|your\s+name|як\s+(тебе|звуть|звати))", text, re.I | re.U):
        return random.choice(_NAME_RESPONSES)
    return random.choice(_SOCIAL_RESPONSES)


# ---------------------------------------------------------------------------
# Memory — 3-turn sliding window (deque of dicts)
# ---------------------------------------------------------------------------

class Memory:
    def __init__(self, maxlen: int = 3) -> None:
        self._buf: deque[dict] = deque(maxlen=maxlen)

    def push(self, role: str, text: str, domain: Domain) -> None:
        self._buf.append({"role": role, "text": text, "domain": domain})

    def last_domain(self) -> Optional[Domain]:
        if self._buf:
            return self._buf[-1]["domain"]
        return None

    def topic_shifted(self, new_domain: Domain) -> bool:
        last = self.last_domain()
        if last is None:
            return False
        return last != new_domain and new_domain not in (Domain.SOCIAL, Domain.UNKNOWN)

    def decay_if_shifted(self, new_domain: Domain) -> None:
        """Pop oldest entry when topic shifts — organic forgetting."""
        if self.topic_shifted(new_domain) and len(self._buf) > 0:
            # Remove oldest entry (deque doesn't have popleft limit here —
            # we simply let maxlen handle it, but force one early eviction)
            try:
                self._buf.popleft()
            except IndexError:
                pass

    def context(self) -> list[dict]:
        return list(self._buf)


# ---------------------------------------------------------------------------
# CartinBrain — central state + response engine
# ---------------------------------------------------------------------------

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

        # ---- Offended state handling ------------------------------------ #
        if self.is_offended:
            if is_art_praise(text):
                # Ice-breaker: high-quality aesthetic compliment lifts the freeze
                self.is_offended    = False
                self.ignore_counter = 0
                self.memory.push("user", text, domain)
                response = random.choice(_ICE_BROKEN_RESPONSES)
                self.memory.push("cartin", response, domain)
                return response
            else:
                self.ignore_counter -= 1
                if self.ignore_counter <= 0:
                    # Counter expired: grudgingly come back, still cold
                    self.is_offended    = False
                    self.ignore_counter = 0
                response = random.choice(_OFFENDED_RESPONSES)
                # Don't update memory during silent treatment
                return response

        # ---- Detect new insult ----------------------------------------- #
        if tone == Tone.INSULT and domain == Domain.ART_DESIGN:
            self.is_offended    = True
            self.ignore_counter = 3
            # First silent response
            return random.choice(_OFFENDED_RESPONSES)

        # ---- Memory decay on topic shift -------------------------------- #
        self.memory.decay_if_shifted(domain)

        # ---- Route to domain response ----------------------------------- #
        if domain == Domain.ART_DESIGN:
            response = _art_reply(text, tone)

        elif domain == Domain.TECH_WEAPONS:
            response = _tech_reply(text)

        elif domain == Domain.COOKING_HOME:
            response = random.choice(_COOKING_RESPONSES)

        elif domain == Domain.SOCIAL:
            response = _social_reply(text)

        else:  # UNKNOWN
            response = random.choice(_UNKNOWN_RESPONSES)

        # ---- Persist to memory ----------------------------------------- #
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

# Single shared brain instance (stateful per server process)
_brain = CartinBrain()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    offended: bool
    ignore_counter: int
    domain: str


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
    """Debug endpoint — inspect cartin's current mood and memory."""
    return {
        "is_offended":    _brain.is_offended,
        "ignore_counter": _brain.ignore_counter,
        "memory":         _brain.memory.context(),
    }


@app.post("/reset")
def reset() -> dict:
    """Hard-reset brain state (useful for testing)."""
    global _brain
    _brain = CartinBrain()
    return {"status": "reset"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=False)

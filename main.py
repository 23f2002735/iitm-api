from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re, json, sys, traceback
from io import StringIO
from datetime import timedelta
from youtube_transcript_api import YouTubeTranscriptApi

app = FastAPI()

# ================= CORS =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 1️⃣ COMMENT SENTIMENT
# ============================================================

class CommentRequest(BaseModel):
    comment: str


@app.post("/comment")
def comment(req: CommentRequest):
    text = req.comment.lower()

    if any(w in text for w in ["good","great","amazing","love","excellent"]):
        return {"sentiment": "positive", "rating": 5}

    if any(w in text for w in ["bad","worst","hate","terrible","awful"]):
        return {"sentiment": "negative", "rating": 1}

    return {"sentiment": "neutral", "rating": 3}

# ============================================================
# 2️⃣ CODE INTERPRETER
# ============================================================

class CodeRequest(BaseModel):
    code: str


def run_code(code: str):
    old = sys.stdout
    sys.stdout = StringIO()
    try:
        exec(code)
        return True, sys.stdout.getvalue()
    except Exception:
        return False, traceback.format_exc()
    finally:
        sys.stdout = old


def extract_error_line(tb: str):
    m = re.search(r'line (\d+)', tb)
    if m:
        return [int(m.group(1))]
    return []


@app.post("/code-interpreter")
def code_interpreter(req: CodeRequest):
    ok, out = run_code(req.code)

    if ok:
        return {"error": [], "result": out}

    return {"error": extract_error_line(out), "result": out}

# ============================================================
# 3️⃣ YOUTUBE ASK
# ============================================================

class AskRequest(BaseModel):
    video_url: str
    topic: str


def to_hhmmss(sec: float):
    return str(timedelta(seconds=int(sec))).rjust(8, "0")


def extract_video_id(url: str):
    m = re.search(r"(?:v=|youtu.be/)([\w-]{11})", url)
    return m.group(1) if m else None


@app.post("/ask")
def ask(req: AskRequest):
    vid = extract_video_id(req.video_url)
    if not vid:
        raise HTTPException(400, "Invalid YouTube URL")

    transcript = YouTubeTranscriptApi.get_transcript(vid)

    topic = req.topic.lower()

    for entry in transcript:
        if topic in entry["text"].lower():
            return {
                "timestamp": to_hhmmss(entry["start"]),
                "video_url": req.video_url,
                "topic": req.topic
            }

    return {
        "timestamp": "00:00:00",
        "video_url": req.video_url,
        "topic": req.topic
    }

# ============================================================
# 4️⃣ FUNCTION CALLING (ROBUST)
# ============================================================

@app.get("/execute")
def execute(q: str = Query(...)):
    ql = q.lower()

    # ---------- ticket status ----------
    m = re.search(r"ticket\s*(\d+)", ql)
    if m and ("status" in ql or "ticket" in ql):
        return {
            "name": "get_ticket_status",
            "arguments": json.dumps({"ticket_id": int(m.group(1))})
        }

    # ---------- schedule meeting ----------
    m = re.search(r"(\d{4}-\d{2}-\d{2})", ql)
    t = re.search(r"(\d{2}:\d{2})", ql)
    r = re.search(r"room\s*([a-z0-9 ]+)", ql)
    if "schedule" in ql and m and t and r:
        return {
            "name": "schedule_meeting",
            "arguments": json.dumps({
                "date": m.group(1),
                "time": t.group(1),
                "meeting_room": r.group(1).strip().title()
            })
        }

    # ---------- expense ----------
    m = re.search(r"employee\s*(\d+)", ql)
    if m and "expense" in ql:
        return {
            "name": "get_expense_balance",
            "arguments": json.dumps({"employee_id": int(m.group(1))})
        }

    # ---------- bonus ----------
    m = re.search(r"employee\s*(\d+)", ql)
    y = re.search(r"(20\d{2})", ql)
    if m and y and "bonus" in ql:
        return {
            "name": "calculate_performance_bonus",
            "arguments": json.dumps({
                "employee_id": int(m.group(1)),
                "current_year": int(y.group(1))
            })
        }

    # ---------- issue ----------
    c = re.search(r"issue\s*(\d+)", ql)
    d = re.search(r"([a-z ]+)\s*department", ql)
    if c and d:
        return {
            "name": "report_office_issue",
            "arguments": json.dumps({
                "issue_code": int(c.group(1)),
                "department": d.group(1).strip().title()
            })
        }

    return {"name": "unknown", "arguments": "{}"}

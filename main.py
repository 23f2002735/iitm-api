from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import re, json, sys, traceback
from io import StringIO
from datetime import timedelta
from youtube_transcript_api import YouTubeTranscriptApi

app = FastAPI()

# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 1️⃣ COMMENT SENTIMENT  (NO API KEY)
# ============================================================

class CommentRequest(BaseModel):
    comment: str


def simple_sentiment(text: str):
    t = text.lower()

    positive_words = ["good", "great", "amazing", "love", "excellent", "nice"]
    negative_words = ["bad", "worst", "hate", "terrible", "awful"]

    if any(w in t for w in positive_words):
        return {"sentiment": "positive", "rating": 5}
    if any(w in t for w in negative_words):
        return {"sentiment": "negative", "rating": 1}

    return {"sentiment": "neutral", "rating": 3}


@app.post("/comment")
def comment(req: CommentRequest):
    if not req.comment.strip():
        raise HTTPException(400, "Empty comment")
    return simple_sentiment(req.comment)


# ============================================================
# 2️⃣ CODE INTERPRETER
# ============================================================

class CodeRequest(BaseModel):
    code: str


def execute_python(code: str):
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        exec(code)
        output = sys.stdout.getvalue()
        return True, output
    except Exception:
        tb = traceback.format_exc()
        return False, tb
    finally:
        sys.stdout = old_stdout


def extract_error_line(tb: str):
    """
    Extract ONLY the real user-code line number.
    Avoid matching library/internal lines.
    """
    matches = re.findall(r'line (\d+)', tb)
    if not matches:
        return []
    return [int(matches[-1])]  # last occurrence = real line


@app.post("/code-interpreter")
def code_interpreter(req: CodeRequest):
    ok, out = execute_python(req.code)

    if ok:
        return {"error": [], "result": out}

    lines = extract_error_line(out)
    return {"error": lines, "result": out}


# ============================================================
# 3️⃣ YOUTUBE ASK
# ============================================================

class AskRequest(BaseModel):
    video_url: str
    topic: str


def hhmmss(seconds):
    return str(timedelta(seconds=int(seconds))).rjust(8, "0")


def extract_video_id(url: str):
    m = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
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
                "timestamp": hhmmss(entry["start"]),
                "video_url": req.video_url,
                "topic": req.topic
            }

    return {
        "timestamp": "00:00:00",
        "video_url": req.video_url,
        "topic": req.topic
    }


# ============================================================
# 4️⃣ FUNCTION CALLING
# ============================================================

@app.get("/execute")
def execute(q: str = Query(...)):
    ql = q.lower()

    # Ticket status
    m = re.search(r"ticket\s+(\d+)", ql)
    if m and "status" in ql:
        return {
            "name": "get_ticket_status",
            "arguments": json.dumps({
                "ticket_id": int(m.group(1))
            })
        }

    # Schedule meeting
    m = re.search(r"(\d{4}-\d{2}-\d{2}).*?(\d{2}:\d{2}).*?room\s+([a-z0-9 ]+)", ql)
    if m and "schedule" in ql:
        return {
            "name": "schedule_meeting",
            "arguments": json.dumps({
                "date": m.group(1),
                "time": m.group(2),
                "meeting_room": m.group(3).strip().title()
            })
        }

    # Expense
    m = re.search(r"employee\s+(\d+)", ql)
    if m and "expense" in ql:
        return {
            "name": "get_expense_balance",
            "arguments": json.dumps({
                "employee_id": int(m.group(1))
            })
        }

    # Bonus
    m = re.search(r"employee\s+(\d+).*?(\d{4})", ql)
    if m and "bonus" in ql:
        return {
            "name": "calculate_performance_bonus",
            "arguments": json.dumps({
                "employee_id": int(m.group(1)),
                "current_year": int(m.group(2))
            })
        }

    # Office issue
    c = re.search(r"issue\s+(\d+)", ql)
    d = re.search(r"for the\s+([a-z ]+)\s+department", ql)
    if c and d:
        return {
            "name": "report_office_issue",
            "arguments": json.dumps({
                "issue_code": int(c.group(1)),
                "department": d.group(1).strip().title()
            })
        }

    return {
        "name": "unknown",
        "arguments": json.dumps({})
    }

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import re, json, sys, traceback, os
from io import StringIO
from datetime import timedelta
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai   # optional (used in code-interpreter AI)

app = FastAPI()

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 1️⃣ COMMENT SENTIMENT (NO OPENAI)
# =========================

class CommentRequest(BaseModel):
    comment: str


@app.post("/comment")
def comment(req: CommentRequest):
    text = req.comment.lower()

    positive_words = ["good", "great", "amazing", "love", "excellent", "happy"]
    negative_words = ["bad", "terrible", "awful", "hate", "worst", "poor"]

    if any(w in text for w in positive_words):
        sentiment = "positive"
        rating = 5
    elif any(w in text for w in negative_words):
        sentiment = "negative"
        rating = 1
    else:
        sentiment = "neutral"
        rating = 3

    return {
        "sentiment": sentiment,
        "rating": rating
    }

# =========================
# 2️⃣ CODE INTERPRETER
# =========================

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
        return False, traceback.format_exc()
    finally:
        sys.stdout = old_stdout


def analyze_error_local(code: str, tb: str):
    """
    Fallback: extract line numbers from traceback without AI
    """
    lines = re.findall(r"line (\d+)", tb)
    return [int(x) for x in lines] if lines else []


@app.post("/code-interpreter")
def code_interpreter(req: CodeRequest):
    ok, out = execute_python(req.code)

    if ok:
        return {"error": [], "result": out}

    # try local extraction first
    lines = analyze_error_local(req.code, out)

    return {"error": lines, "result": out}

# =========================
# 3️⃣ YOUTUBE ASK
# =========================

class AskRequest(BaseModel):
    video_url: str
    topic: str


def hhmmss(sec):
    return str(timedelta(seconds=int(sec))).rjust(8, "0")


def extract_video_id(url):
    m = re.search(r"(?:v=|youtu.be/)([\w-]{11})", url)
    return m.group(1) if m else None


@app.post("/ask")
def ask(req: AskRequest):
    video_id = extract_video_id(req.video_url)

    if not video_id:
        raise HTTPException(400, "Invalid YouTube URL")

    transcript = YouTubeTranscriptApi.get_transcript(video_id)

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

# =========================
# 4️⃣ FUNCTION CALLING
# =========================

@app.get("/execute")
def execute(q: str = Query(...)):
    ql = q.lower()

    m = re.search(r"ticket (\d+)", ql)
    if "status" in ql and m:
        return {
            "name": "get_ticket_status",
            "arguments": json.dumps({"ticket_id": int(m.group(1))})
        }

    m = re.search(r"(\d{4}-\d{2}-\d{2}).*(\d{2}:\d{2}).*room ([a-z0-9 ]+)", ql)
    if "schedule" in ql and m:
        return {
            "name": "schedule_meeting",
            "arguments": json.dumps({
                "date": m.group(1),
                "time": m.group(2),
                "meeting_room": m.group(3).strip().title()
            })
        }

    m = re.search(r"employee (\d+)", ql)
    if "expense" in ql and m:
        return {
            "name": "get_expense_balance",
            "arguments": json.dumps({"employee_id": int(m.group(1))})
        }

    m = re.search(r"employee (\d+).*?(\d{4})", ql)
    if "bonus" in ql and m:
        return {
            "name": "calculate_performance_bonus",
            "arguments": json.dumps({
                "employee_id": int(m.group(1)),
                "current_year": int(m.group(2))
            })
        }

    c = re.search(r"issue (\d+)", ql)
    d = re.search(r"for the ([a-z ]+) department", ql)
    if "issue" in ql and c and d:
        return {
            "name": "report_office_issue",
            "arguments": json.dumps({
                "issue_code": int(c.group(1)),
                "department": d.group(1).title()
            })
        }

    return {"error": "No match"}

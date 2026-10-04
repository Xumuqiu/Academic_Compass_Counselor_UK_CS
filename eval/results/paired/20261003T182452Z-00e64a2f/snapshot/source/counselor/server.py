"""本地交互服务：可选结构化 CV 输入与三步会话 API。"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from .data import load_case, list_programmes
from .config import mode, model_config, read_settings
from .cv import case_from_cv
from .domain import accept_answer, make_brief, new_state, next_question
from .llm import suggest_angle
from .data import PROGRAMMES
from .document import export_docx
from .intake import cv_from_document, normalize_cv
from .llm import (extract_cv, generate_full_brief, parse_experience_answer,
                  review_full_brief_claims)
from .claim_check import checked_proposals, propose_narrowings
from .workflow import (answer_question, make_result, next_question as full_next_question,
                       progress as full_progress, start_case)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
SAMPLE_CV = Path(__file__).resolve().parent.parent / "data" / "sample_cv.json"
SESSIONS = {}
FULL_SESSIONS = {}
LOCK = threading.Lock()
MAX_BODY = 7_000_000


def full_public_state(sid, state):
    return {
        "session_id": sid,
        "student": state["case"]["student"]["label"],
        "programmes": state["programmes"],
        "subjects": state["case"]["student"]["subjects"],
        "records": state["records"], "round": state["round"],
        "progress": full_progress(state),
        "question": full_next_question(state),
        "can_finish": True,
    }


def public_state(sid, state, case, is_demo):
    return {
        "session_id": sid,
        "student": case["student"]["label"],
        "experience": case["student"]["experience"]["title"],
        "subjects": case["student"]["subjects"],
        "programme": case["programme"],
        "is_demo": is_demo,
        "round": state["round"],
        "question": next_question(state),
        "values": state["values"],
        "sources": state["sources"],
        "skipped": state["skipped"]
    }


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("请求长度不合法") from exc
        if length < 1 or length > MAX_BODY:
            raise ValueError("请求体为空或过大")
        try:
            item = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise ValueError("请求不是合法 JSON") from exc
        if not isinstance(item, dict):
            raise ValueError("请求必须是 JSON 对象")
        return item

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/full/export/"):
            sid = path.rsplit("/", 1)[-1]
            with LOCK:
                session = FULL_SESSIONS.get(sid)
            if session is None or session["result"] is None:
                self.respond(404, {"error": "结果不存在，请先生成头脑风暴素材包"})
                return
            data = export_docx(session["result"])
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            self.send_header("Content-Disposition", f'attachment; filename="brainstorm_{sid[:8]}.docx"')
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/programmes":
            self.respond(200, {"programmes": list_programmes()})
            return
        if path == "/sample-cv.json":
            data = SAMPLE_CV.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=sample_cv.json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        files = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                 "/full.js": ("full.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
        if path not in files:
            self.respond(404, {"error": "页面不存在"})
            return
        filename, content_type = files[path]
        data = (WEB_DIR / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in {"/api/start", "/api/answer", "/api/finish",
                        "/api/full/start", "/api/full/answer", "/api/full/finish"}:
            self.respond(404, {"error": "接口不存在"})
            return
        try:
            body = self.read_json()
            if path == "/api/full/start":
                ids = body.get("program_ids")
                if ids is None:
                    ids = [body.get("program_id", "manchester_cs_ug")]
                if not isinstance(ids, list) or not ids or len(ids) > len(PROGRAMMES) \
                        or not all(isinstance(i, str) for i in ids) \
                        or len(set(ids)) != len(ids):
                    raise ValueError("请从已收录项目中选择至少一个目标项目")
                programmes = [p for p in PROGRAMMES if p["id"] in ids]
                if len(programmes) != len(ids):
                    raise ValueError("目标项目不在当前收录范围内")
                if "cv" in body:
                    cv = normalize_cv(body["cv"])
                elif "file" in body:
                    file = body["file"]
                    if not isinstance(file, dict):
                        raise ValueError("file 必须是对象")
                    cv = cv_from_document(file.get("name"), file.get("content_base64"), extract_cv)
                else:
                    cv = normalize_cv(json.loads(SAMPLE_CV.read_text(encoding="utf-8")))
                state = start_case(cv, programmes)
                sid = uuid4().hex
                with LOCK:
                    FULL_SESSIONS[sid] = state
                self.respond(200, full_public_state(sid, state))
                return
            if path in ("/api/full/answer", "/api/full/finish"):
                sid = body.get("session_id")
                if not isinstance(sid, str):
                    raise ValueError("缺少 session_id")
                with LOCK:
                    state = FULL_SESSIONS.get(sid)
                if state is None:
                    self.respond(404, {"error": "会话已失效，请重新开始"})
                    return
                if path == "/api/full/answer":
                    if state["finished"]:
                        raise ValueError("结果已生成；请重新开始新的案例")
                    parser = parse_experience_answer if mode() == "live" else None
                    updated = answer_question(state, body.get("answer"), parse=parser)
                    with LOCK:
                        FULL_SESSIONS[sid] = updated
                    self.respond(200, full_public_state(sid, updated))
                    return
                if state["result"] is None:
                    proposal, usage = generate_full_brief(state)
                    if proposal is None:
                        checked, questions = None, []
                    else:
                        try:
                            review, _ = review_full_brief_claims(state, proposal)
                        except RuntimeError:
                            review = None
                        narrowed = propose_narrowings(proposal, review)
                        narrow_review = None
                        if narrowed.get("materials") or narrowed.get("thesis_claim"):
                            try:
                                narrow_review, _ = review_full_brief_claims(state, narrowed)
                            except RuntimeError:
                                pass
                        checked, questions = checked_proposals(
                            state, proposal, review, narrow_review)
                    result = make_result(state, checked)
                    result["open_questions"].extend(questions)
                    with LOCK:
                        state["result"] = result
                        state["model_usage"] = usage
                        state["finished"] = True
                self.respond(200, state["result"])
                return
            if path == "/api/start":
                program_id = body.get("program_id", "manchester_cs_ug")
                if not isinstance(program_id, str):
                    raise ValueError("program_id 必须是项目编号")
                case_template = load_case(program_id)
                is_demo = "cv" not in body
                case = case_template if is_demo else case_from_cv(body["cv"], case_template)
                sid = uuid4().hex
                state = new_state(case)
                with LOCK:
                    SESSIONS[sid] = {"case": case, "is_demo": is_demo, "state": state, "brief": None}
                self.respond(200, public_state(sid, state, case, is_demo))
                return
            sid = body.get("session_id")
            if not isinstance(sid, str):
                raise ValueError("缺少 session_id")
            with LOCK:
                session = SESSIONS.get(sid)
            if session is None:
                self.respond(404, {"error": "会话已失效，请重新开始"})
                return
            if path == "/api/answer":
                answer = body.get("answer")
                if not isinstance(answer, str):
                    raise ValueError("answer 必须是文字")
                with LOCK:
                    if session["brief"] is not None:
                        raise ValueError("结果已生成，请重新开始")
                    session["state"] = accept_answer(session["state"], answer)
                    state = session["state"]
                self.respond(200, public_state(sid, state, session["case"], session["is_demo"]))
                return
            if session["brief"] is None:
                suggestion, usage = suggest_angle(session["case"], session["state"])
                with LOCK:
                    session["brief"] = make_brief(session["case"], session["state"], suggestion, usage)
            self.respond(200, session["brief"])
        except (ValueError, RuntimeError) as exc:
            self.respond(400, {"error": str(exc)})


def main():
    settings = read_settings()
    current_mode = mode()
    config = model_config(require_key=current_mode == 'live')
    port = int(settings.get("COUNSELOR_PORT", "8010"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"UK CS Counselor Workbench: http://127.0.0.1:{port}")
    print("模式: " + current_mode)
    print(f"模型: {config.provider} / {config.model}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime

app = Flask(__name__)

# 집에서 실행 중인 n8n Webhook 기본 주소
BASE_N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_BASE_URL", "https://newzips.iptime.org")

# 요청 로그를 저장할 리스트 (최대 1000건 유지)
request_logs = []
MAX_LOGS = 1000

@app.route("/webhook", methods=["POST"])
@app.route("/webhook-test", methods=["POST"])
def slack_webhook():
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "path": request.path,
        "form": request.form.to_dict(),
        "json": request.get_json(silent=True)
    }

    # Slack Event API가 URL 인증을 시도할 경우
    if log_entry["json"] and log_entry["json"].get("type") == "url_verification":
        _add_log(log_entry)
        return log_entry["json"].get("challenge", ""), 200, {"Content-Type": "text/plain"}

    # Slack Slash Command는 form-urlencoded 형식으로 옴
    text = request.form.get("text")
    user = request.form.get("user_name")
    command = request.form.get("command")

    # 요청 경로 그대로 사용하여 n8n으로 전달
    full_url = BASE_N8N_WEBHOOK_URL + request.path

    payload = {
        "text": text,
        "user": user,
        "command": command
    }

    try:
        r = requests.post(full_url, json=payload, timeout=3)
        r.raise_for_status()
        log_entry["status"] = "success"
        _add_log(log_entry)
        return "명령이 전달되었습니다.", 200
    except Exception as e:
        log_entry["status"] = "error"
        log_entry["error"] = str(e)
        _add_log(log_entry)
        return f"전달 실패: {str(e)}", 500

@app.route("/", methods=["GET"])
def index():
    return "Flask 중계 서버가 작동 중입니다. 이 서버는 Slack 요청을 중계하여 n8n으로 전달합니다."

@app.route("/test", methods=["GET"])
def test():
    return jsonify({
        "status": "ok",
        "message": "테스트 페이지입니다. 이 페이지는 Render 배포 상태 확인용입니다."
    })

@app.route("/logs", methods=["GET"])
@app.route("/logs/<int:count>", methods=["GET"])
def get_logs(count=50):
    count = min(count, MAX_LOGS)
    return jsonify({
        "count": len(request_logs),
        "logs": request_logs[-count:]
    })

def _add_log(entry):
    request_logs.append(entry)
    if len(request_logs) > MAX_LOGS:
        del request_logs[0:len(request_logs) - MAX_LOGS]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

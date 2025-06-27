from flask import Flask, request, Response
import requests
import os

app = Flask(__name__)

N8N_BASE = os.getenv("N8N_WEBHOOK_BASE_URL", "http://localhost:5678")

request_logs = []

@app.route('/', defaults={'path': ''}, methods=['POST'])
@app.route('/<path:path>', methods=['POST'])
def proxy(path):
    full_path = '/' + path
    print(f"📥 Incoming POST to {full_path}")
    print("Headers:", dict(request.headers))
    print("Body:", request.data)

    # Slack challenge 처리
    if request.is_json:
        try:
            data = request.get_json()
            print("Parsed JSON:", data)
            if data.get("type") == "url_verification":
                return data.get("challenge", ""), 200, {"Content-Type": "text/plain"}
        except Exception as e:
            print("JSON parse error:", e)

    # 로그 저장
    request_logs.append({
        "path": full_path,
        "headers": dict(request.headers),
        "body": request.get_json(silent=True)
    })
    if len(request_logs) > 1000:
        request_logs.pop(0)

    try:
        # n8n으로 프록시 전송
        target_url = f"{N8N_BASE}{full_path}"
        resp = requests.post(
            target_url,
            headers=request.headers,
            data=request.data,
            timeout=5
        )
        return Response(resp.content, status=resp.status_code, content_type=resp.headers.get("Content-Type"))
    except Exception as e:
        print("Proxy error:", e)
        return "Proxy Error", 502

@app.route('/test')
def test():
    return {"status": "ok", "message": "proxy is working"}, 200

@app.route('/log', defaults={'count': 50})
@app.route('/log/<int:count>')
def view_logs(count):
    count = min(count, 1000)
    return {"logs": request_logs[-count:]}, 200

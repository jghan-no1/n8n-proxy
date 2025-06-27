from flask import Flask, request, jsonify
import requests
import os
import threading
from queue import Queue

app = Flask(__name__)

class SlackEvent:
    def __init__(self):
        # Base URL for N8N webhooks (e.g. "https://my-n8n-instance.com/webhook")
        self.n8n_base = os.getenv("N8N_WEBHOOK_BASE_URL", "http://localhost:5678")
        # Slack bot token (optional for chat.postMessage)
        self.slack_bot_token = os.getenv("SLACK_BOT_TOKEN", "token-to-user-value")
        # Queue for incoming Slack events
        self.queue = Queue()
        # Start a single background worker thread
        worker = threading.Thread(target=self._process_queue, daemon=True)
        worker.start()

    def send_slack_message(self, response_url: str, message: str):
        """
        Send a follow-up message to Slack using the provided response_url.
        """
        try:
            requests.post(response_url, json={"text": message}, timeout=5)
        except Exception as e:
            app.logger.error(f"Failed sending Slack message: {e}")

    def forward_to_n8n(self, subpath: str, body: dict, response_url: str):
        """
        Forward the Slack payload to the corresponding N8N webhook and handle errors/timeouts.
        """
        target_url = f"{self.n8n_base}/{subpath}"
        try:
            resp = requests.post(target_url, json=body, timeout=20)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            error_msg = "N8N 요청이 시간 초과되었습니다."
            self.send_slack_message(response_url, error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"N8N 요청 중 오류 발생: {e}"
            self.send_slack_message(response_url, error_msg)

    def _process_queue(self):
        """
        Worker loop to process queued Slack events sequentially.
        """
        while True:
            subpath, body, response_url = self.queue.get()
            try:
                self.forward_to_n8n(subpath, body, response_url)
            except Exception as e:
                app.logger.error(f"Error processing Slack event: {e}")
            finally:
                self.queue.task_done()

# Instantiate the SlackEvent handler
slack_event = SlackEvent()

@app.route('/slack/<path:subpath>', methods=['POST'])
def slack_proxy(subpath):
    # Slack URL verification (Events API)
    if request.is_json:
        data = request.get_json()
        if data.get("type") == "url_verification":
            return jsonify({"challenge": data.get("challenge")}), 200

    # Parse payload (supports slash commands and events)
    if request.form:
        payload = request.form.to_dict()
    else:
        payload = request.get_json(silent=True) or {}

    # Extract Slack response_url for follow-up messages
    response_url = payload.get("response_url")

    # Enqueue task and immediately acknowledge
    slack_event.queue.put((subpath, payload, response_url))
    ack_message = "지금 처리중이니 잠시만 기다려 주세요..."
    return jsonify({"text": ack_message}), 200

@app.route('/log', methods=['GET', 'POST'])
def log_route():
    # Simple log endpoint to inspect incoming data
    data = request.get_json(silent=True) or request.args.to_dict()
    app.logger.info(f"Log endpoint received: {data}")
    return jsonify({"status": "logged", "data": data}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 10000)))

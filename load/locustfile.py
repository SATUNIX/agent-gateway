from __future__ import annotations

import json
import random

from locust import HttpUser, between, task


class GatewayUser(HttpUser):
    wait_time = between(0.5, 2.0)
    headers = {"Content-Type": "application/json", "x-api-key": "dev-secret"}
    models = ["default/assistant", "labs/my_sdk_agent", "smoke"]

    @task(7)
    def non_streaming_request(self):
        model = random.choice(self.models)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Summarize the latest findings."}],
            "stream": False,
        }
        self.client.post(
            "/v1/chat/completions",
            headers=self.headers,
            data=json.dumps(payload),
            name="chat-completion",
        )

    @task(3)
    def streaming_request(self):
        model = random.choice(self.models)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Stream this response."}],
            "stream": True,
        }
        self.client.post(
            "/v1/chat/completions",
            headers=self.headers,
            data=json.dumps(payload),
            name="chat-completion-stream",
        )

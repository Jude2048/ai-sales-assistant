import os
import json
import urllib.request
import urllib.error


class InstagramAdapter:

    def __init__(self):
        self.access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")

    def send(self, recipient: str, message: str):
        url = (
            f"https://graph.instagram.com/v26.0/"
            f"{self.instagram_account_id}/messages"
        )

        payload = {
            "recipient": {
                "id": recipient
            },
            "message": {
                "text": message
            }
        }

        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))

            print("INSTAGRAM MESSAGE SENT:", result)

            return result

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            print("INSTAGRAM SEND ERROR:", error_body)
            raise
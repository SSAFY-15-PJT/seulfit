from django.conf import settings
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

url = "https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"

payload = {
      "contents": [
          {
              "parts": [
                  {
                      "text": "Provide a quick recipe for pasta in Korean."
                  }
              ]
          }
      ]
  }

req = Request(
      url,
      data=json.dumps(payload).encode("utf-8"),
      headers={
          "Content-Type": "application/json",
          "x-goog-api-key": settings.VLM_API_KEY,
      },
      method="POST",
  )

print({"url": url, "payload_keys": list(payload.keys())})

try:
      res = urlopen(req, timeout=30)
      print("OK", res.status)
      print(res.read().decode("utf-8")[:1000])
except HTTPError as e:
      print("HTTPError", e.code)
      print(e.read().decode("utf-8")[:1000])
except Exception as e:
      print(type(e).__name__, str(e))
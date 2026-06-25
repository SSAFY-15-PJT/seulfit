from django.conf import settings
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

url ="https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"

  # 1x1 transparent PNG
png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="

cases = [
      (
          "camel_inlineData",
          {
              "contents": [
                  {
                      "parts": [
                          {"text": "이 이미지를 한 문장으로 설명해줘."},
                          {
                              "inlineData": {
                                  "mimeType": "image/png",
                                  "data": png_base64,
                              }
                          },
                      ]
                  }
              ]
          },
      ),
      (
          "snake_inline_data",
          {
              "contents": [
                  {
                      "parts": [
                          {"text": "이 이미지를 한 문장으로 설명해줘."},
                          {
                              "inline_data": {
                                  "mime_type": "image/png",
                                  "data": png_base64,
                              }
                          },
                      ]
                  }
              ]
          },
      ),
  ]

for name, payload in cases:
      req = Request(
          url,
          data=json.dumps(payload).encode("utf-8"),
          headers={
              "Content-Type": "application/json",
              "x-goog-api-key": settings.VLM_API_KEY,
          },
          method="POST",
      )

      print("CASE", name, "payload_keys", list(payload.keys()))
      try:
          res = urlopen(req, timeout=30)
          print("OK", res.status)
          print(res.read().decode("utf-8")[:500])
      except HTTPError as e:
          print("HTTPError", e.code)
          print(e.read().decode("utf-8")[:500])
      except Exception as e:
          print(type(e).__name__, str(e))
      print("---")
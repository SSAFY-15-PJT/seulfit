# VLM GMS Debug Notes

## Current Status

- Frontend upload flow is connected to the backend VLM parser.
- Uploaded image results are saved under the logged-in `user_id`.
- Recommendation recalculation uses the saved consumption profile.
- The system still falls back to `mock_vision_parser` for the real image upload path.
- The latest frontend console showed:

```json
{
  "source": "mock_vision_parser",
  "vlm_status": "fallback",
  "vlm_error_type": "http_error",
  "vlm_error": "HTTP 400: ... GenerateContentRequest.contents: contents is not specified",
  "vlm_request_debug": {
    "api_type": "gemini_generate_content",
    "model": "gemini-3.5-flash",
    "payload_keys": ["contents"],
    "has_contents": true,
    "content_count": 1,
    "media": {
      "original_bytes": 341492,
      "sent_bytes": 79753,
      "sent_mime_type": "image/jpeg",
      "resized": true
    }
  }
}
```

## Environment Used

Expected `.env` shape:

```env
GMS_KEY=...
VLM_API_TYPE=gemini_generate_content
VLM_API_URL=https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent
VLM_MODEL=gemini-3.5-flash
VLM_GMS_COMPAT=true
VLM_GMS_STRICT=true
```

Frontend Vite proxy points to:

```js
target: "http://127.0.0.1:8001"
```

So the backend must be started with:

```bash
python manage.py runserver 127.0.0.1:8001
```

## What Was Confirmed

### 1. Frontend and Auth Flow

- The frontend sends VLM upload requests after login.
- `user_id` is no longer hardcoded to `1`.
- Uploaded report save flow uses the current logged-in user.
- CSRF handling was added:
  - `GET /api/v1/auth/status/` sets a CSRF cookie.
  - Frontend sends `X-CSRFToken` on mutating requests.
  - Frontend retries once after a CSRF 403.

### 2. OpenAI GMS Text Request Works

Text-only OpenAI GMS request succeeded:

```json
{
  "model": "gpt-5",
  "messages": [
    {"role": "developer", "content": "Answer in Korean"},
    {"role": "user", "content": "hello"}
  ]
}
```

Result:

```text
OK 200
```

### 3. OpenAI GMS Image Request Failed

OpenAI `chat/completions` image input failed even after:

- `VLM_MODEL=gpt-5`
- `VLM_GMS_COMPAT=true`
- `VLM_GMS_STRICT=true`
- Removing `response_format`
- Removing `temperature`
- Removing `max_tokens`
- Matching the GMS quick example structure as closely as possible

Error:

```text
[GMS error] Model not found in request for domain api.openai.com
```

Conclusion:

- OpenAI text-only is supported.
- OpenAI image content-array payload is not working through this GMS route.
- The OpenAI route is not currently suitable for the image-to-JSON VLM flow unless GMS provides a specific image input example.

### 4. Gemini GMS Text Request Works

Gemini text-only request to:

```text
https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent
```

with:

```json
{
  "contents": [
    {
      "parts": [
        {"text": "Provide a quick recipe for pasta in Korean."}
      ]
    }
  ]
}
```

Result:

```text
OK 200
```

### 5. Gemini Small Image Request Works

Manual 1x1 PNG tests succeeded for both variants:

```json
{
  "contents": [
    {
      "parts": [
        {"text": "Describe this image."},
        {
          "inlineData": {
            "mimeType": "image/png",
            "data": "base64..."
          }
        }
      ]
    }
  ]
}
```

and:

```json
{
  "contents": [
    {
      "parts": [
        {"text": "Describe this image."},
        {
          "inline_data": {
            "mime_type": "image/png",
            "data": "base64..."
          }
        }
      ]
    }
  ]
}
```

Both returned:

```text
OK 200
```

### 6. Actual Uploaded Image Still Fails

Real uploaded image flow currently fails with:

```text
GenerateContentRequest.contents: contents is not specified
```

even though backend debug says:

```json
{
  "payload_keys": ["contents"],
  "has_contents": true,
  "content_count": 1
}
```

This suggests the request body is built correctly in Django, but GMS/Gemini does not receive or parse it as expected for the real uploaded image payload.

## Changes Already Made

### Backend

File:

```text
backend/hyperlocal/services.py
```

Implemented:

- OpenAI `chat_completions` mode.
- OpenAI `responses` mode.
- Gemini `generateContent` mode:
  - `VLM_API_TYPE=gemini_generate_content`
  - `x-goog-api-key` header
  - `contents[].parts[]` payload
  - `inlineData.mimeType/data` image payload
  - Gemini response parser using `candidates[].content.parts[].text`
- VLM debug fields:
  - `vlm_status`
  - `vlm_error_type`
  - `vlm_error`
  - `vlm_request_debug`
- Media debug fields:
  - `original_bytes`
  - `sent_bytes`
  - `original_mime_type`
  - `sent_mime_type`
  - `base64_chars`
  - `resized`
  - `width`
  - `height`
- Image resizing before VLM request:
  - Max size currently `1280x1280`
  - JPEG quality currently `85`

### Frontend

File:

```text
frontend/src/App.vue
```

Implemented:

- Console output for:
  - `source`
  - `vlm_status`
  - `vlm_error_type`
  - `vlm_error`
  - `vlm_request_debug`

### Dependencies

File:

```text
backend/requirements.txt
```

Added:

```text
Pillow>=10.0,<12.0
```

## Most Likely Cause

The most likely remaining cause is payload/body handling by the GMS Gemini proxy when the actual uploaded image is included.

Evidence:

- Gemini text-only request works.
- Gemini 1x1 image request works.
- Actual uploaded image request fails.
- The backend debug confirms `contents` exists.
- The actual uploaded image was reduced from about `341 KB` to about `79 KB`, but still failed.

Current hypothesis:

- The real image payload is still too large or otherwise causes the GMS proxy to fail request body parsing.
- The proxy then forwards an empty or malformed body to Gemini, leading Gemini to say:

```text
GenerateContentRequest.contents: contents is not specified
```

## Next Steps

### Step 1. Make Uploaded Image Payload Smaller

Reduce VLM media more aggressively:

- Max dimension: `512px`
- JPEG quality: `60`
- Target payload: ideally under `30 KB`

Expected debug target:

```json
{
  "media": {
    "sent_bytes": 30000,
    "base64_chars": 40000,
    "resized": true
  }
}
```

### Step 2. Shorten Prompt

Current prompt is relatively long. For Gemini testing, use a shorter prompt:

```text
Extract spending amounts from this image. Return JSON only:
{"spending":{"cafe":0,"convenience":0,"dining":0,"delivery":0,"mart":0,"shopping":0},"confidence":0,"summary":""}
```

### Step 3. Add Deeper Debug

Add these fields to `vlm_request_debug`:

```json
{
  "parts_count": 2,
  "part_keys": [["text"], ["inlineData"]],
  "has_inlineData": true,
  "inlineData_mimeType": "image/jpeg"
}
```

### Step 4. Retest Actual Upload

After Step 1-3:

```bash
python manage.py runserver 127.0.0.1:8001
```

Then upload the same image again.

### Step 5. If Still Failing

If the reduced image still fails with:

```text
contents is not specified
```

then request the exact GMS image analysis example from the VLM team or GMS documentation.

Needed example:

```text
URL
Headers
Body JSON
Image input format
Maximum accepted image size
Maximum accepted body size
```

## Operational Recommendation

For the demo, the current fallback path is still useful:

- Upload image.
- Store parsed/fallback spending profile.
- Trigger Python recommendation core.
- Trigger GraphDB recommendation/rerank.
- Show dashboard/profile updates.

But the UI/log should treat:

```text
source: mock_vision_parser
```

as a fallback parser result, not a real VLM result.


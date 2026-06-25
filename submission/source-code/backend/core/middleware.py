class SimpleCorsMiddleware:
    """Small dev CORS middleware for the Vite frontend."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        origin = request.headers.get("Origin", "")
        allowed_origins = {"http://localhost:5173", "http://127.0.0.1:5173"}
        response["Access-Control-Allow-Origin"] = origin if origin in allowed_origins else "http://localhost:5173"
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        response["Access-Control-Allow-Credentials"] = "true"
        return response

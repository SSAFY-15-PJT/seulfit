from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404


def vue_index(request, path=""):
    index_path = Path(settings.BASE_DIR).parent / "frontend" / "dist" / "index.html"
    if not index_path.exists():
        raise Http404("Frontend build not found. Run `npm run build` in frontend/.")
    return FileResponse(index_path.open("rb"), content_type="text/html")

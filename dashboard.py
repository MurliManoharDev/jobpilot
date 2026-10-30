"""Serve the progress dashboard at http://127.0.0.1:8000 (browsers can't read local CSV files directly)."""
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import config

PORT = 8000
ALLOWED = {"/": "dashboard.html", "/dashboard.html": "dashboard.html", "/applications_history.csv": config.HISTORY_FILE.name,
    "/linkedin_history.csv": config.LINKEDIN_HISTORY_FILE.name,
}


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path not in ALLOWED:
            self.send_error(404)
            return
        self.path = "/" + ALLOWED[path]
        super().do_GET()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=str(config.BASE_DIR)))
    url = f"http://127.0.0.1:{PORT}"
    print(f"Dashboard running at {url} (Ctrl+C to stop)")
    webbrowser.open(url)
    server.serve_forever()

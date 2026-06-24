"""Serve output/apply_list.html on localhost and open it in the browser."""
import http.server
import os
import webbrowser
from functools import partial

PORT = 8000
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def main():
    html_path = os.path.join(OUTPUT_DIR, "apply_list.html")
    if not os.path.exists(html_path):
        print("No apply_list.html found. Run 'just search' first.")
        raise SystemExit(1)

    os.chdir(OUTPUT_DIR)

    handler = partial(
        http.server.SimpleHTTPRequestHandler,
        directory=OUTPUT_DIR,
    )

    with http.server.HTTPServer(("127.0.0.1", PORT), handler) as httpd:
        url = f"http://localhost:{PORT}/apply_list.html"
        print(f"Serving at {url}  (Ctrl+C to stop)")
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()

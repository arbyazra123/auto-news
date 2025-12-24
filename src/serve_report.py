#!/usr/bin/env python3
"""
Simple web server to serve daily_report.md as HTML
Serves on 0.0.0.0:1313
"""

import http.server
import socketserver
import os
from pathlib import Path
import markdown
from datetime import datetime
from zoneinfo import ZoneInfo

PORT = 1313
HOST = "0.0.0.0"


class ReportHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()

            # Read and convert markdown to HTML
            try:
                report_file = "daily_report.md"
                with open(report_file, "r", encoding="utf-8") as f:
                    md_content = f.read()

                # Get file modification time in Jakarta timezone
                file_mtime = os.path.getmtime(report_file)
                jakarta_tz = ZoneInfo("Asia/Jakarta")
                file_date = datetime.fromtimestamp(file_mtime, tz=jakarta_tz).strftime("%Y-%m-%d %H:%M:%S %Z")

                # Convert markdown to HTML
                html_content = markdown.markdown(
                    md_content,
                    extensions=['extra', 'codehilite', 'tables']
                )

                # Wrap in nice HTML template
                full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Stock Analysis Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 5px;
        }}
        .subtitle {{
            color: #7f8c8d;
            font-size: 14px;
            margin-top: 5px;
            margin-bottom: 20px;
            font-style: italic;
        }}
        h2 {{
            color: #2980b9;
            margin-top: 30px;
        }}
        h3 {{
            color: #34495e;
        }}
        code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background-color: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        blockquote {{
            border-left: 4px solid #3498db;
            padding-left: 20px;
            margin-left: 0;
            color: #555;
            font-style: italic;
        }}
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        hr {{
            border: none;
            border-top: 2px solid #eee;
            margin: 30px 0;
        }}
        .refresh-btn {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: #3498db;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }}
        .refresh-btn:hover {{
            background: #2980b9;
        }}
    </style>
</head>
<body>
    <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
    <div class="container">
        <div class="subtitle">Report generated: {file_date}</div>
        {html_content}
    </div>
    <script>
        // Auto-refresh every 5 minutes
        setTimeout(function(){{
            location.reload();
        }}, 300000);
    </script>
</body>
</html>
"""
                self.wfile.write(full_html.encode('utf-8'))

            except FileNotFoundError:
                error_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Report Not Found</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
        }}
        .error {{
            color: #e74c3c;
            font-size: 24px;
        }}
    </style>
</head>
<body>
    <div class="error">
        <h1>⚠️ Report Not Found</h1>
        <p>daily_report.md does not exist yet.</p>
        <p>Please run: <code>bash run_daily_analysis.sh</code></p>
    </div>
</body>
</html>
"""
                self.wfile.write(error_html.encode('utf-8'))

        else:
            super().do_GET()


def main():
    # Change to script directory
    os.chdir(Path(__file__).parent)

    with socketserver.TCPServer((HOST, PORT), ReportHandler) as httpd:
        print("=" * 60)
        print(f"📊 Daily Report Server Running")
        print("=" * 60)
        print(f"\n🌐 Server started at: http://{HOST}:{PORT}")
        print(f"📁 Serving from: {os.getcwd()}")
        print(f"\n📝 Open in browser: http://localhost:{PORT}")
        print(f"\n🔄 Auto-refreshes every 5 minutes")
        print(f"\nPress Ctrl+C to stop the server\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Server stopped.")


if __name__ == "__main__":
    main()

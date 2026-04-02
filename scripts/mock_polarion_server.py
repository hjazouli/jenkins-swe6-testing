from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import sys

class PolarionMockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        print(f"\n[Mock Polarion Server] Received data for {self.path}")
        print(f"[Mock Polarion Server] Payload:\n{post_data.decode('utf-8')}")
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")

def run_server(port=8081):
    server_address = ('', port)
    httpd = HTTPServer(server_address, PolarionMockHandler)
    print(f"Mock Polarion Server running on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    try:
        run_server()
    except KeyboardInterrupt:
        print("\nStopping Mock Polarion Server...")
        sys.exit(0)

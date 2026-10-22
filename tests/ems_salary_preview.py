"""Local UI test server backed by isolated in-memory EMS fixtures."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from test_ems_salary import SalaryTests

fixture = SalaryTests()
fixture.setUp()
fixture.setup_salary()
fixture.client.app.mount('/static', StaticFiles(directory=Path(__file__).resolve().parents[1] / 'static'))


class Handler(BaseHTTPRequestHandler):
    def handle_request(self):
        path = self.path.removeprefix('/erp')
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        response = fixture.client.request(self.command, path, content=body,
                                         headers={'Content-Type': self.headers.get('Content-Type', '')})
        self.send_response(response.status_code)
        for key, value in response.headers.items():
            if key.lower() not in ('content-length', 'transfer-encoding'):
                self.send_header(key, value)
        self.send_header('Content-Length', str(len(response.content)))
        self.end_headers()
        self.wfile.write(response.content)

    do_GET = do_POST = do_PUT = handle_request


if __name__ == '__main__':
    print('Isolated EMS UI preview: http://127.0.0.1:8016/erp/ems', flush=True)
    try:
        HTTPServer(('127.0.0.1', 8016), Handler).serve_forever()
    finally:
        fixture.tearDown()

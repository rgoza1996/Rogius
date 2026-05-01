import urllib.request
import urllib.error
import urllib.parse
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, "./src/tui")
from api_server import app

client = TestClient(app)
try:
    response = client.get("/chats/..%2f..%2f.env")
    print(response.status_code)
    print(response.json())
except Exception as e:
    print(e)

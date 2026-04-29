import urllib.request
import json

req = urllib.request.Request(
    'http://127.0.0.1:8000/multistep/execute-agentic-stream',
    method='POST',
    data=json.dumps({
        'goal': 'Open google.com, search for hello world, and take a screenshot',
        'steps': []
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

with urllib.request.urlopen(req) as res:
    with open('curl_output.txt', 'w', encoding='utf-8') as f:
        for line in res:
            f.write(line.decode('utf-8'))

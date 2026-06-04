import urllib.request, json, sys

def req(method, path, data=None, token=None, timeout=15):
    url = f'http://localhost:8080{path}'
    body = json.dumps(data).encode() if data else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=timeout)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode()).get('detail', '')
        except Exception:
            detail = 'unknown'
        return {'status': e.code, 'detail': detail}
    except Exception as e:
        return {'error': str(e)}

# Login
r = req('POST', '/api/auth/login', {'username': 'admin', 'password': 'admin123'})
tok = r.get('access_token', '')
print('Token:', bool(tok))

# Check LLM status
llm = req('GET', '/api/llm-status', token=tok)
print('LLM status:', llm)

# Chat diagnose
diag = req('GET', '/api/chat/diagnose', token=tok)
print('Chat diagnose:', diag)

# Test chat
print()
print('Sending chat message...')
chat = req('POST', '/api/chat', {'message': 'What is the current network status?', 'mode': 'technical'}, token=tok, timeout=25)
print('Chat response:')
for k, v in chat.items():
    print(f'  {k}: {v}')

"""Quick test: call nexus-chat model directly."""
import http.client, json, time

conn = http.client.HTTPConnection("localhost", 11434, timeout=30)
payload = json.dumps({
    "model": "nexus-chat",
    "prompt": "Say hello in one short sentence.",
    "stream": False,
    "options": {"temperature": 0.3, "num_ctx": 512},
})

t0 = time.time()
conn.request("POST", "/api/generate", body=payload,
             headers={"Content-Type": "application/json"})
print(f"Request sent, waiting (timeout=30s)...")
resp = conn.getresponse()
body = resp.read().decode()
elapsed = time.time() - t0

if resp.status == 200:
    data = json.loads(body)
    reply = data.get("response", "")
    print(f"OK  Status={resp.status}  Time={elapsed:.1f}s")
    print(f"Reply ({len(reply)} chars): {reply[:200]}")
else:
    print(f"FAIL  Status={resp.status}  Time={elapsed:.1f}s")
    print(f"Body: {body[:300]}")

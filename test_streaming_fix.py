"""Test the fixed chat_agent with streaming."""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

from root.chat_agent import chat_with_llm, reset_chat_cache

# Reset any cached state
reset_chat_cache()

# Clear trace log
trace_log = r"C:\Users\USER\Desktop\JOSHUA!!\implementation\chat_trace.log"
with open(trace_log, "w") as f:
    f.write("")

print("=" * 60)
print("Testing chat_with_llm with streaming mode...")
print("=" * 60)

t0 = time.time()
result = chat_with_llm("What is the current network status?", mode="technical")
elapsed = time.time() - t0

print(f"\nTime:   {elapsed:.1f}s")
print(f"Source: {result.get('source', '?')}")
print(f"Reply:  {result.get('reply', '(empty)')[:300]}")
print(f"\n{'SUCCESS' if result.get('source') in ('llm',) else 'CHECK - source is: ' + result.get('source', '?')}")

import os
import requests
import json
import time
import sys

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

def print_separator():
    print("\n" + "="*80 + "\n")

def test_chat():
    print("🌿 IP-SAKTI Legal RAG Chat CLI")
    print_separator()
    
    # 1. Start Server Health Check
    try:
        res = requests.get(f"{BASE_URL}/health", timeout=5)
        if res.status_code != 200:
            print(f"❌ Server returned non-200 status code: {res.status_code} ({res.text})")
            return
        health = res.json()
        print(f"✅ Backend Health: {health.get('status', 'unknown')}")
    except requests.exceptions.ConnectionError:
        print(f"❌ ERROR: FastAPI backend server is not running on {BASE_URL}")
        print("Please start the backend with: `uvicorn app.main:app --port 8001`")
        return

    session_id = None
    
    print("\nStarting Chat Session... (Type 'exit' to quit)")
    
    while True:
        try:
            query = input("\n👤 You: ").strip()
            if not query:
                continue
            if query.lower() in ['exit', 'quit']:
                break
                
            print("🤖 Thinking (querying LM Studio via FastAPI)...")
            
            payload = {
                "message": query,
                "top_k": 4
            }
            if session_id:
                payload["session_id"] = session_id
                
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/chat", json=payload)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                session_id = data["session_id"]
                
                print(f"\n🧠 Answer ({elapsed:.2f}s):\n{data['answer']}")
                
                print("\n📚 Sources Cited:")
                for idx, src in enumerate(data['sources'], 1):
                    print(f"  [{idx}] {src['title']} ({src['provision']}) - Pages {src['pages']}")
                
                print(f"\n[Session ID: {session_id} | Turn: {data['turn_index']}]")
            else:
                print(f"ERROR {response.status_code}: {response.text}")
                
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    test_chat()

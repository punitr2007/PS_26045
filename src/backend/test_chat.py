#!/usr/bin/env python3
"""
IP-SAKTI Legal RAG - Chatbot Test Script

Test the legal RAG chatbot on a single message, an interactive multi-turn session,
or via HTTP against a running FastAPI backend server.

Usage:
    # 1. Test with default sample message (direct in-process mode):
    python test_chat.py

    # 2. Test with a custom message:
    python test_chat.py "Can I patent an Ayurvedic formulation with turmeric in India?"

    # 3. Interactive multi-turn chat in terminal (tests slot-filling & clarification):
    python test_chat.py -i

    # 4. Test via running HTTP server (http://127.0.0.1:8001):
    python test_chat.py --http "What is Section 3(p) of the Indian Patents Act?"

    # 5. Pre-seed known facts (power user ingress):
    python test_chat.py "Is this patentable?" --facts '{"category": "proprietary", "jurisdiction": "india"}'
"""

import sys
import os
import time
import uuid
import json
import argparse
import asyncio
from typing import Optional, Dict, Any

# Configure UTF-8 encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure backend root is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


DEFAULT_TEST_MESSAGE = "Can I patent an Ayurvedic herbal formulation containing turmeric and ginger in India?"


def print_separator(char="=", length=70):
    print(char * length)


def print_response(result: Dict[str, Any], elapsed_time: float, mode: str = "direct"):
    """Pretty prints the chatbot response and retrieved evidence sources."""
    print_separator("-")
    session_id = result.get("session_id", "N/A")
    status = result.get("status", "unknown")
    turn_index = result.get("turn_index", 1)
    
    status_display = f"[{status.upper()}]" if status else "[UNKNOWN]"
    print(f"Mode: {mode.upper()} | Session: {session_id} | Turn: #{turn_index} | Latency: {elapsed_time:.2f}s")
    print(f"Status: {status_display}")
    print_separator("-")

    # If the system asked clarification questions
    questions = result.get("questions") or []
    if status == "needs_clarification" or questions:
        print("\n🤔 [CLARIFICATION REQUIRED BY BOT]:")
        for idx, q in enumerate(questions, 1):
            field = q.get("field", "information")
            question_text = q.get("question", str(q))
            options = q.get("options", [])
            print(f"  {idx}. [{field.upper()}] {question_text}")
            if options:
                print(f"     Options: {', '.join(options)}")
        print()

    # Chatbot Answer
    answer = result.get("answer", "")
    print("🤖 [CHATBOT ANSWER]:")
    if answer:
        print(answer.strip())
    else:
        print("  (No textual answer returned)")
    print()

    # Retrieved Citations / Sources
    sources = result.get("sources", [])
    if sources:
        print(f"📚 [RETRIEVED LEGAL SOURCES ({len(sources)})]:")
        for i, src in enumerate(sources, 1):
            provision = src.get("provision", "N/A")
            title = src.get("title", "Unknown Title")
            chapter = src.get("chapter", "N/A")
            pages = src.get("pages", "N/A")
            print(f"  {i}. {provision} - \"{title}\" (Chapter: {chapter}, Pages: {pages})")
    else:
        print("📚 [RETRIEVED LEGAL SOURCES]: None (Direct response or chitchat bypass)")

    print_separator("=")


async def test_direct(
    message: str,
    session_id: Optional[str] = None,
    top_k: int = 4,
    known_facts: Optional[Dict[str, Any]] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """Tests chatbot directly via python service layer (no HTTP server required)."""
    from app.services.chatbot_service import chatbot_service
    from app.services.memory_service import memory_service

    if not session_id:
        session_id = memory_service.create_session()

    if verbose:
        print(f"[VERBOSE] Initializing chatbot_service with session_id={session_id}...")

    start = time.time()
    result = await chatbot_service.process_chat_async(
        session_id=session_id,
        query=message,
        top_k=top_k,
        known_facts=known_facts
    )
    elapsed = time.time() - start

    if verbose:
        print(f"[VERBOSE] Raw result: {json.dumps(result, indent=2, default=str)}")

    print_response(result, elapsed, mode="Direct Service")
    return result


def test_http(
    message: str,
    base_url: str = "http://127.0.0.1:8001",
    session_id: Optional[str] = None,
    top_k: int = 4,
    known_facts: Optional[Dict[str, Any]] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """Tests chatbot by sending an HTTP POST request to a running FastAPI backend."""
    import requests

    endpoint = f"{base_url.rstrip('/')}/api/v1/chat"
    payload = {
        "message": message,
        "top_k": top_k
    }
    if session_id:
        payload["session_id"] = session_id
    if known_facts:
        payload["known_facts"] = known_facts

    if verbose:
        print(f"[VERBOSE] Sending HTTP POST to {endpoint} with payload:\n{json.dumps(payload, indent=2)}")

    start = time.time()
    try:
        response = requests.post(endpoint, json=payload, timeout=120)
        elapsed = time.time() - start
    except requests.exceptions.ConnectionError:
        print(f"\n❌ [ERROR] Could not connect to backend server at {base_url}!")
        print("   Make sure the backend is running with:")
        print("   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload")
        print("   Or run without '--http' to test directly in-process.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ [ERROR] HTTP request failed: {e}")
        sys.exit(1)

    if response.status_code != 200:
        print(f"\n❌ [ERROR] Server returned HTTP {response.status_code}: {response.text}")
        sys.exit(1)

    result = response.json()
    if verbose:
        print(f"[VERBOSE] Raw response: {json.dumps(result, indent=2)}")

    print_response(result, elapsed, mode="HTTP API")
    return result


async def interactive_mode(
    use_http: bool = False,
    base_url: str = "http://127.0.0.1:8001",
    top_k: int = 4,
    verbose: bool = False
):
    """Run an interactive multi-turn session directly from the CLI."""
    session_id = str(uuid.uuid4())
    mode_str = f"HTTP ({base_url})" if use_http else "Direct In-Process"
    
    print_separator("=")
    print("🚀 IP-SAKTI CHATBOT INTERACTIVE TEST CONSOLE")
    print(f"Session ID : {session_id}")
    print(f"Mode       : {mode_str}")
    print("Commands   : Type 'exit', 'quit' or 'q' to end the session.")
    print("             Type 'history' to inspect full session memory turns.")
    print_separator("=")

    while True:
        try:
            user_msg = input("\n👤 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting interactive test session.")
            break

        if not user_msg:
            continue
        if user_msg.lower() in ("exit", "quit", "q"):
            print("Session ended.")
            break

        if user_msg.lower() == "history":
            if use_http:
                import requests
                hist_url = f"{base_url.rstrip('/')}/api/v1/chat/{session_id}/history"
                try:
                    h_res = requests.get(hist_url)
                    print(json.dumps(h_res.json(), indent=2))
                except Exception as ex:
                    print(f"Failed to fetch history: {ex}")
            else:
                from app.services.memory_service import memory_service
                turns = memory_service.get_history(session_id)
                print(f"History turns ({len(turns)}): {json.dumps(turns, indent=2, default=str)}")
            continue

        if use_http:
            test_http(
                message=user_msg,
                base_url=base_url,
                session_id=session_id,
                top_k=top_k,
                verbose=verbose
            )
        else:
            await test_direct(
                message=user_msg,
                session_id=session_id,
                top_k=top_k,
                verbose=verbose
            )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test the IP-SAKTI Legal RAG Chatbot with a message, multi-turn session, or HTTP endpoint.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help=f"User message/query to send to the chatbot (default: '{DEFAULT_TEST_MESSAGE}')"
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run an interactive multi-turn session in the terminal."
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Send request via HTTP to a running FastAPI backend instead of direct in-process."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8001",
        help="Backend base URL for HTTP testing (default: http://127.0.0.1:8001)."
    )
    parser.add_argument(
        "-s", "--session-id",
        default=None,
        help="Custom session ID (useful to continue an existing conversation turn)."
    )
    parser.add_argument(
        "-k", "--top-k",
        type=int,
        default=4,
        help="Number of retrieved legal chunks to return (default: 4)."
    )
    parser.add_argument(
        "--facts",
        type=str,
        default=None,
        help="JSON string of pre-seeded known facts (e.g. '{\"jurisdiction\":\"india\",\"category\":\"proprietary\"}')"
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Fetch and display stored conversation history after completing the turn."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose logs and raw JSON responses."
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Parse facts if provided
    known_facts = None
    if args.facts:
        try:
            known_facts = json.loads(args.facts)
        except Exception as e:
            print(f"❌ [ERROR] Invalid JSON passed to --facts: {e}")
            sys.exit(1)

    # Interactive mode
    if args.interactive:
        asyncio.run(interactive_mode(
            use_http=args.http,
            base_url=args.url,
            top_k=args.top_k,
            verbose=args.verbose
        ))
        return

    # Single message mode
    message = args.message or DEFAULT_TEST_MESSAGE
    print_separator("=")
    print("💬 TESTING IP-SAKTI CHATBOT")
    print(f"Query: \"{message}\"")
    if known_facts:
        print(f"Pre-seeded Facts: {known_facts}")
    print_separator("=")

    if args.http:
        res = test_http(
            message=message,
            base_url=args.url,
            session_id=args.session_id,
            top_k=args.top_k,
            known_facts=known_facts,
            verbose=args.verbose
        )
    else:
        res = asyncio.run(test_direct(
            message=message,
            session_id=args.session_id,
            top_k=args.top_k,
            known_facts=known_facts,
            verbose=args.verbose
        ))

    # Display history if requested
    if args.history and res:
        session_id = res.get("session_id")
        print("\n📜 [STORED CONVERSATION HISTORY]:")
        from app.services.memory_service import memory_service
        turns = memory_service.get_history(session_id)
        print(json.dumps(turns, indent=2, default=str))


if __name__ == "__main__":
    main()

"""Test script to debug chats endpoint"""
import requests
import sys

# Test the chats endpoint
try:
    print("Testing http://127.0.0.1:8000/chats...")
    r = requests.get('http://127.0.0.1:8000/chats', timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Content: {r.text[:1000]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    sys.exit(1)

import requests

# Local Ollama default port configuration
OLLAMA_URL = "http://localhost:11434/api/generate"

payload = {
    "model": "llama3.1",
    "prompt": "Explain the concept of 'Groundedness' in LLM evaluation in one sentence.",
    "stream": False
}

try:
    response = requests.post(OLLAMA_URL, json=payload)
    if response.status_code == 200:
        print("🎉 Success! Local LLM Response:")
        print(response.json().get("response"))
    else:
        print(f"❌ Server error: {response.status_code}")
except Exception as e:
    print(f"❌ Connection failed. Is the Ollama background app running? Error: {e}")

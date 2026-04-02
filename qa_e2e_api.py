import time
import requests
import sys

BASE_URL = "http://localhost:8000/api/v1"
REPO_URL = "https://github.com/pallets/itsdangerous"
BRANCH = "main"

def log(msg):
    print(f"[*] {msg}")

def check(condition, msg):
    if not condition:
        print(f"[!] FAILED: {msg}")
        sys.exit(1)

def poll_status(repo_id, expected_status, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        res = requests.get(f"{BASE_URL}/repos/{repo_id}")
        check(res.status_code == 200, f"Failed to get repo for polling: {res.text}")
        status = res.json().get("status")
        if status == expected_status:
            return True
        if status == "failed":
            print(f"[!] Repo status failed: {res.json()}")
            return False
        time.sleep(2)
    print(f"[!] Timeout waiting for status {expected_status}")
    return False

def run_tests():
    # 1. Health
    res = requests.get(f"{BASE_URL}/health")
    check(res.status_code == 200, "Health endpoint")
    log("Health OK")

    # 2. Add repo
    res = requests.post(f"{BASE_URL}/repos", json={"repo_url": REPO_URL, "branch": BRANCH})
    check(res.status_code == 201, f"Create repo failed: {res.text}")
    repo = res.json()
    repo_id = repo["id"]
    log(f"Created repo {repo_id}")

    # 3. Wait for indexed
    log("Waiting for indexing to complete...")
    check(poll_status(repo_id, "indexed"), "Indexing")
    log("Indexed OK")

    # 4. Trigger parse
    log("Triggering parse...")
    res = requests.post(f"{BASE_URL}/repos/{repo_id}/parse")
    check(res.status_code == 202, f"Parse trigger failed: {res.text}")
    log("Waiting for parsing to complete...")
    check(poll_status(repo_id, "parsed"), "Parsing")
    log("Parsed OK")

    # 5. Trigger embed
    log("Triggering embed...")
    res = requests.post(f"{BASE_URL}/repos/{repo_id}/embed")
    check(res.status_code in [200, 202], f"Embed trigger failed: {res.text}")
    log("Waiting for embedding to complete...")
    check(poll_status(repo_id, "embedded"), "Embedding")
    log("Embedded OK")

    # 6. Semantic Search
    log("Testing Semantic Search...")
    res = requests.post(f"{BASE_URL}/repos/{repo_id}/search", json={"query": "Where is the Flask app created?", "top_k": 5})
    check(res.status_code == 200, f"Search failed: {res.text}")
    data = res.json()
    check(len(data.get("items", [])) > 0, "No search results")
    log(f"Search OK: found {len(data.get('items', []))} results")

    # 7. Ask Repo
    log("Testing Ask Repo...")
    res = requests.post(f"{BASE_URL}/repos/{repo_id}/ask", json={"question": "Where is the config loaded?"})
    check(res.status_code == 200, f"Ask failed: {res.text}")
    data = res.json()
    check("answer" in data, "No answer in chat response")
    log("Ask OK")

    # 8. Hotspots
    log("Testing Hotspots...")
    res = requests.get(f"{BASE_URL}/repos/{repo_id}/hotspots")
    check(res.status_code == 200, f"Hotspots failed: {res.text}")
    log("Hotspots OK")

    # 9. Onboarding
    log("Testing Onboarding Generate...")
    res = requests.post(f"{BASE_URL}/repos/{repo_id}/onboarding/generate", json={"top_files": 5, "include_hotspots": True, "include_search_context": True})
    check(res.status_code == 200, f"Onboarding POST Generate failed: {res.text}")
    log("Testing Onboarding GET...")
    res = requests.get(f"{BASE_URL}/repos/{repo_id}/onboarding")
    check(res.status_code == 200, f"Onboarding GET failed: {res.text}")
    log("Onboarding OK")

    # 10. PR Impact
    log("Testing PR Impact...")
    res = requests.post(f"{BASE_URL}/repos/{repo_id}/impact", json={"changed_files": ["src/app.py"]})
    check(res.status_code == 200, f"PR Impact failed: {res.text}")
    log("PR Impact OK")

    log("ALL E2E API TESTS PASSED!")

if __name__ == "__main__":
    run_tests()

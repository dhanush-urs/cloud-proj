import urllib.request
import json
import traceback

try:
    req = urllib.request.Request("http://localhost:8000/api/v1/repos")
    with urllib.request.urlopen(req) as response:
        repos = json.loads(response.read().decode())
    
    for repo in repos.get('items', []):
        if repo['status'] == 'indexed':
            repo_id = repo['id']
            print(f"Repo ID (indexed): {repo_id}")
            break
except Exception as e:
    traceback.print_exc()


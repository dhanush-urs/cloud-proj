import time
import requests

start = time.time()
resp = requests.post('http://localhost:8000/api/v1/repos', json={'repo_url':'https://github.com/dhanush-urs/TestRepo', 'branch':'main'})
print("Took:", time.time() - start)
print(resp.status_code, resp.text)

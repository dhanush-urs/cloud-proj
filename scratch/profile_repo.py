import time
import requests

t0 = time.time()
resp = requests.post('http://localhost:8000/api/v1/repos', json={'repo_url':'https://github.com/dhanush-urs/TestRepo3', 'branch':'main'})
t1 = time.time()
print("Total Time:", t1 - t0)

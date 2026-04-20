import requests

resp = requests.post('http://localhost:8000/api/v1/repos', json={'repo_url':'https://github.com/dhanush-urs/TestRepo', 'branch':'main'})
print("Status:", resp.status_code)
print(resp.text)

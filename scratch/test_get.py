import requests

resp = requests.get('http://localhost:8000/api/v1/repos/cf3f7280-508d-4824-b0cd-8bae4021e07f')
print(resp.status_code)
print(resp.text)

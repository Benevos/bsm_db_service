import requests

json = {
    "operation": "search",
    "parameters": {
        "id": 1
    }
}

response = requests.post("http://localhost:44000/operation", json=json)
print(response.json())
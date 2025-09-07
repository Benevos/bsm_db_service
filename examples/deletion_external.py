import requests

json = {
    "operation": "delete",
    "parameters": {
        "id": "2",
    }
}

response = requests.post("http://localhost:44000/operation", json=json)
print(response.json())

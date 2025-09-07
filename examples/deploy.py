import requests

json = {
    "operation": "delete",
    "parameters": {
        "id": "my_id_02",
    }
}

response = requests.post("http://localhost:44000/op", json=json)
print(response.json())

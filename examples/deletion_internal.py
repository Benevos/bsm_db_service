import requests

json = {
    "operation": "deploy",
    "parameters": {
        "id": "my_id_02",
        "tags": {
            "demography": {
            "age": 18,
            "gender": "man"
            },
            "method": "jumping"
        },
        "connection": {
            "port": 45003,
            "manager": "mongodb",
        }
    }
}

response = requests.post("http://localhost:44000/operation", json=json)
print(response.json())

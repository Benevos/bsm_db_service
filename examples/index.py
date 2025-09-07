import requests

json = {
    "operation": "index",
    "parameters": {
        "id": "1",
        "tags": {
            "demography": {
            "age": 20,
            "gender": "woman"
            },
            "method": "poisoning"
        },
        "connection": {
            "ip": "127.0.0.1",
            "port": 27017,
            "manager": "mongodb",
        }
    }
}

response = requests.post("http://localhost:44000/operation", json=json)
print(response.json())

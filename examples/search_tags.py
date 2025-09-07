import requests

json = {
    "operation": "search",
    "parameters": {
        "tags": {
            "demography": {
                "gender":  {"$in": ["woman", "man"]},
            }
        }
    }
}

response = requests.post("http://localhost:44000/op", json=json)
print(response.json())

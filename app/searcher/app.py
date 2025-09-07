from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from dotenv import load_dotenv, find_dotenv
import httpx
import asyncio
import logging
import os
import re

class TagsSearchRequest(BaseModel):
    tags: dict
    
class IDSearchRequest(BaseModel):
    id: str

ON_CONATAINER = True

if not ON_CONATAINER:
    load_dotenv(find_dotenv())

DBINDEX_IP = os.getenv("DBINDEX_IP", "dbindex")
DBINDEX_PORT = os.getenv("DBINDEX_PORT", 27017)
DBINDEX_ADDRESS = f"mongodb://{DBINDEX_IP}:{DBINDEX_PORT}"
DBINDEX_DB_NAME = os.getenv("DBINDEX_DB_NAME", "dbindex")
DBINDEX_COLLECTION_NAME = os.getenv("DBINDEX_COLLECTION_NAME", "databases")

async def connect_to_service(service_name: str, service_address: str, retries: int = None):

    logger.info(f"Connecting to '{service_name}' at {service_address}")
    
    async with httpx.AsyncClient() as client:
        attempt = 0
        while retries is None or attempt < retries:
            try:
                response = await client.get(f"{service_address}/health")
                response.raise_for_status()
                logger.info(f"Successfully connected to '{service_name}' at {service_address}")
                break
            except Exception as e:
                attempt += 1
                logger.error(f"Failed to connect to '{service_name}' at {service_address} (attempt {attempt}): {e}")
                await asyncio.sleep(2)
        
        return None

async def connect_to_mongodb(service_name: str, service_address: str, client: MongoClient, retries: int = None):

    logger.info(f"Connecting to '{service_name}' at {service_address}")

    while retries is None or attempt < retries:
        attempt = 0
        try:
            client.server_info()
            logger.info(f"Successfully connected to '{service_name}' at {service_address}")
            break
        except Exception as e:
            attempt += 1
            logger.error(
                f"Failed to connect to '{service_name}' at {service_address} (attempt {attempt}): {e}"
            )
            await asyncio.sleep(2)

    return None

def flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, dict):
            if any(subkey.startswith("$") for subkey in v.keys()):
                items.append((new_key, v))
            else:
                items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))

    return dict(items)

logger = logging.getLogger("uvicorn.error")
client: MongoClient | None = None

async def lifespan(app: FastAPI):
    logger.info(f"Starting service 'SEARCHER'")
    
    client = MongoClient(DBINDEX_ADDRESS)
    
    await connect_to_mongodb("DBINDEX", DBINDEX_ADDRESS, client)
    
    yield 
    
    logger.info("Shutting down service SEARCHER")
    
app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/tags")
async def search_tags(request: TagsSearchRequest):
    
    if not request.tags:
        return JSONResponse(status_code=400, content={"message": "Tags dictionary is empty"})
    
    client = MongoClient(DBINDEX_ADDRESS)
    db = client[DBINDEX_DB_NAME]
    collection = db[DBINDEX_COLLECTION_NAME]
    
    normalized_tags = flatten_dict(request.tags, parent_key="tags")
    
    #? Interperter
    
    mongo_query = normalized_tags
    
    logger.info(mongo_query)
    
    try:
        results = list(collection.find(mongo_query, {"_id": 0}))
    except OperationFailure as e:
        return JSONResponse(status_code=400, content={"message": f"{e.details.get('codeName')}: {e.details.get('errmsg')}"})

    if not results:
        return {"message": "No results found",
                "results": []}
                            
    
    return {"message": f"Found {len(results)} results", 
            "results": results}
                        

@app.post("/id")
async def search_by_id(request: IDSearchRequest):
    
    
    if not request.id:
        return JSONResponse(status_code=400, content={"message":"ID is empty"})
    
    client = MongoClient(DBINDEX_ADDRESS)
    db = client[DBINDEX_DB_NAME]
    collection = db[DBINDEX_COLLECTION_NAME]
    
    result = collection.find_one({"id": request.id}, {"_id": 0})
    
    if not result:
        return {"message": f"No result found for ID {request.id}", 
                "result": None}
    
    return {"message": f"Found result for ID {request.id}", 
            "result": result}

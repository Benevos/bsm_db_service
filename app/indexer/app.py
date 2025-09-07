from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv, find_dotenv
from typing import Optional
import asyncio
import logging
import httpx
import os

class ConnectionData(BaseModel):
    ip: str
    port: int
    manager: str
    external: bool

class IndexRequest(BaseModel):
    id: str
    tags: dict
    connection: ConnectionData
    
class DeleteRequest(BaseModel):
    id: str

ON_CONATAINER = True

if not ON_CONATAINER:
    load_dotenv(find_dotenv())

DBINDEX_IP = os.getenv("DBINDEX_IP", "dbindex")
DBINDEX_PORT = os.getenv("DBINDEX_PORT", 27017)
DBINDEX_ADDRESS = f"mongodb://{DBINDEX_IP}:{DBINDEX_PORT}"

SEARCHER_IP = os.getenv("SEARCHER_IP", "searcher")
SEARCHER_PORT = os.getenv("SEARCHER_PORT", 46000)
SEARCHER_ADDRESS = f"http://{SEARCHER_IP}:{SEARCHER_PORT}"

DBINDEX_DB_NAME = os.getenv("DBINDEX_DB_NAME", "dbindex")
DBINDEX_COLLECTION_NAME = os.getenv("DBINDEX_COLLECTION_NAME", "databases")

logger = logging.getLogger("uvicorn.error")
client: MongoClient | None = None

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
    attempt = 0
    while retries is None or attempt < retries:
        try:
            client.server_info()
            logger.info(f"Successfully connected to '{service_name}' at {service_address}")
            break
        except Exception as e:
            attempt += 1
            logger.error(f"Failed to connect to '{service_name}' at {service_address} (attempt {attempt}): {e}")
            await asyncio.sleep(2)
    return None

async def lifespan(app: FastAPI):
    logger.info(f"Starting service INDEXER")
    await connect_to_service('SEARCHER', SEARCHER_ADDRESS)
    logger.info(f"Connecting to 'DBIndex' at {DBINDEX_ADDRESS}")
    client = MongoClient(DBINDEX_ADDRESS)
    await connect_to_mongodb("DBINDEX", DBINDEX_ADDRESS, client)
    yield
    logger.info("Shutting down service INDEXER")
    
app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/index")
async def index_database(request: IndexRequest):
    
    if request.connection.external:
        return JSONResponse(status_code=400, content={"message": "Indexing external databases is not supported yet"})
    
    if not request.id:
        return JSONResponse(status_code=400, content={"message": "ID is empty"})
    
    if not request.tags:
        return JSONResponse(status_code=400, content={"message": "Tags dictionary is empty"})
    
    client = MongoClient(DBINDEX_ADDRESS)
    db = client[DBINDEX_DB_NAME]
    collection = db[DBINDEX_COLLECTION_NAME]
    
    result = collection.find_one({"id": request.id})
    if result:
        return JSONResponse(status_code=400, content={"message": f"Database with ID {request.id} already indexed"})
    
    document = {
        "id": request.id,
        "tags": request.tags,
        "connection": request.connection.model_dump()
    }
    
    collection.insert_one(document)
    document.pop("_id", None)
    
    return JSONResponse(
        status_code=200,
        content={"message": f"Database with ID {request.id} indexed successfully", "document": document}
    )
    
@app.post("/delete")
async def delete_database(request: DeleteRequest):  
    if not request.id:
        return JSONResponse(status_code=400, content={"message": "ID is empty"})
    
    client = MongoClient(DBINDEX_ADDRESS)
    db = client[DBINDEX_DB_NAME]
    collection = db[DBINDEX_COLLECTION_NAME]
    
    result = collection.find_one({"id": request.id})
    if not result:
        return JSONResponse(status_code=404, content={"message": f"No database found with ID {request.id}"})
    
    collection.delete_one({"id": request.id})
    result.pop("_id", None)
    
    return JSONResponse(
        status_code=200,
        content={"message": f"Database with ID {request.id} deleted successfully", "document": result}
    )

from fastapi import FastAPI, HTTPException, Request, Response
from dotenv import load_dotenv, find_dotenv
import asyncio
import logging
import httpx
import os

ON_CONTAINER = os.getenv("ON_CONTAINER", "true").lower()

if ON_CONTAINER != "true":
    load_dotenv(find_dotenv())

SEARCHER_IP = os.getenv("SEARCHER_IP", "searcher") 
SEARCHER_PORT = os.getenv("SEARCHER_PORT", 46000)
SEARCHER_ADDRESS = f"http://{SEARCHER_IP}:{SEARCHER_PORT}"

INDEXER_IP = os.getenv("INDEXER_IP", "indexer")
INDEXER_PORT = os.getenv("INDEXER_PORT", 47000)
INDEXER_ADDRESS = f"http://{INDEXER_IP}:{INDEXER_PORT}"

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
    
    
async def lifespan(app: FastAPI):
    logger.info(f"Starting service 'INDEX_ACCESS'")
    
    await connect_to_service("SEARCHER", SEARCHER_ADDRESS)
    await connect_to_service("INDEXER", INDEXER_ADDRESS)
    
    yield
    logger.info("Shutting down service 'INDEX_ACCESS'")

app = FastAPI(lifespan=lifespan)
logger = logging.getLogger("uvicorn.error")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(full_path: str, request: Request):
 
    if full_path.startswith("searcher"):
        target_address = SEARCHER_ADDRESS
        full_path = full_path.replace("searcher/", "")
    elif full_path.startswith("indexer"):
        target_address = INDEXER_ADDRESS
        full_path = full_path.replace("indexer/", "")
    else:
        raise HTTPException(status_code=404, detail="Service not found")
    
    logger.info(f"Request to serivice '{target_address}' within the route '/{full_path}' received")

    url = f"{target_address}/{full_path}"

    body = await request.body()
    headers = dict(request.headers)
    params = dict(request.query_params)

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers=headers,
                params=params,
            )
            
            logger.info(f"Successful reponse from '{url}'!")
            
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=resp.headers,
            )
        except httpx.RequestError as e:
            logger.error(f"Error proxying request to {url}: {e}")
            raise HTTPException(status_code=502, detail="Bad Gateway")
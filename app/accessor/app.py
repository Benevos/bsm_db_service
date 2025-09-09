from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv
import logging
import asyncio
import httpx
import os

class OperationRequest(BaseModel):
    operation: str
    parameters: dict

ON_CONATAINER = True

if not ON_CONATAINER:
    load_dotenv(find_dotenv())

PROXIER_IP = os.getenv("PROXIER_IP", "proxier")
PROXIER_PORT = os.getenv("PROXIER_PORT", 45000)
PROXIER_ADDRESS = f"http://{PROXIER_IP}:{PROXIER_PORT}"

DEPLOYER_IP = os.getenv("DEPLOYER_IP", "deployer")
DEPLOYER_PORT = os.getenv("DEPLOYER_PORT", "48000")
DEPLOYER_ADDRESS = f"http://{DEPLOYER_IP}:{DEPLOYER_PORT}"

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
    logger.info("Starting service 'ACCESSOR'")
    
    await connect_to_service("PROXIER", PROXIER_ADDRESS)
    await connect_to_service("DEPLOYER", DEPLOYER_ADDRESS)
    
    logger.info("Service 'ACCESSOR' started successfully")
    
    yield
    
    logger.info("Shutting down service 'ACCESSOR'")

app = FastAPI(lifespan=lifespan)
logger = logging.getLogger("uvicorn.error")

@app.get("/health")
async def health():
    return JSONResponse(status_code=200, content={"message": "ok"})

@app.post("/operation")
async def operation(request: OperationRequest):
    logger.info("Request")
    if request.operation == "index":
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{PROXIER_ADDRESS}/indexer/index", json=request.parameters)
            try: 
                return JSONResponse(status_code=response.status_code, content=response.json()) 
            except Exception as e:
                return JSONResponse(status_code=response.status_code, content={"message": response.text})
    
    elif request.operation == "deploy":
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{DEPLOYER_ADDRESS}/deploy", json=request.parameters)
            try: 
                return JSONResponse(status_code=response.status_code, content=response.json()) 
            except Exception as e:
                return JSONResponse(status_code=response.status_code, content={"message": response.text})
    
    elif request.operation == "delete":
        async with httpx.AsyncClient() as client:  
            try:      
                response = await client.post(f"{PROXIER_ADDRESS}/searcher/id", json={"id": str(request.parameters["id"])})
                data = response.json()
                
                if data["result"] is None:
                    return JSONResponse(status_code=response.status_code, content=response.json())
                
                external = data["result"]["connection"]["external"]
            except Exception as e:
                logger.error("Could not determine if database is external or internal")
                return JSONResponse(status_code=500, content={"message": "Could not determine if database is external or internal"})

            if external is None:
                return JSONResponse(status_code=500, content={"message": "Internal server error"})
            
            if external:
                response = await client.post(f"{PROXIER_ADDRESS}/indexer/index", json=request.parameters)
                try:
                    return JSONResponse(status_code=response.status_code, content=response.json()) 
                except Exception as e:
                    return JSONResponse(status_code=response.status_code, content={"message": response.text})
            elif not external:
                response = await client.post(f"{DEPLOYER_ADDRESS}/delete", json=request.parameters)
                try:
                    return JSONResponse(status_code=response.status_code, content=response.json()) 
                except Exception as e:
                    return JSONResponse(status_code=response.status_code, content={"message": response.text})
    
    elif request.operation == "search":
        id = request.parameters.get("id", None)
        tags = request.parameters.get("tags", None)

        if id and tags:
            return JSONResponse(status_code=400, content={"message": "Can only search by tags or id, please remove one"})

        if id and not tags:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{PROXIER_ADDRESS}/searcher/id", json={"id": str(id)})
                try: 
                    return JSONResponse(status_code=response.status_code, content=response.json()) 
                except Exception as e:
                    return JSONResponse(status_code=response.status_code, content={"message": response.text})
        
        if tags and not id:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{PROXIER_ADDRESS}/searcher/tags", json={"tags": tags})
                try: 
                    return JSONResponse(status_code=response.status_code, content=response.json()) 
                except Exception as e:
                    return JSONResponse(status_code=response.status_code, content={"message": response.text})
        
        else:
            return JSONResponse(status_code=500, content={"message": "Unknown error"})
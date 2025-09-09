import docker.errors
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel
from typing import Optional, Annotated
import docker
import logging
import httpx
import asyncio
import os

class ConnectionData(BaseModel):
    ip: Optional[str] = None
    port: int
    manager: str
    external: Optional[bool] = False

class DeployRequest(BaseModel):
    id: str
    tags: dict
    connection: ConnectionData

class DeleteRequest(BaseModel):
    id: str
    
ON_CONATAINER = True

if not ON_CONATAINER:
    load_dotenv(find_dotenv())
    
PROXIER_IP = os.getenv("PROXIER_IP", "proxier")
PROXIER_PORT = os.getenv("PROXIER_PORT", 45000)
PROXIER_ADDRESS = f"http://{PROXIER_IP}:{PROXIER_PORT}"
NETWORK_NAME = os.getenv("NETWORK_NAME", "bsm_db_service")
DOCKER_SOCK = os.getenv("DOCKER_SOCK", "/var/run/docker.sock")

SUPPORTED_MANAGERS = ["mongodb"]


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
    logger.info("Starting service 'DEPLOYER'")
    
    if not os.path.exists(DOCKER_SOCK):
        logger.error(f"Docker socket not found at '{DOCKER_SOCK}")
        raise RuntimeError("Docker socket not found")
    
    if not os.access(DOCKER_SOCK, os.R_OK | os.W_OK):
        logger.error("Docker socket found but insufficient permissions")
        raise PermissionError("Insufficient permissions for Docker socket")
    
    logger.info("Docker socket found with read/write access")
    
    await connect_to_service("PROXIER", PROXIER_ADDRESS)
    
    logger.info("Service 'DEPLOYER' started succesfully")
    
    yield
    
    logger.info("Shutting down service 'DEPLOYER'")

app = FastAPI(lifespan=lifespan)
logger = logging.getLogger("uvicorn.error")

@app.get("/health")
async def health():
    return JSONResponse(content={"message": "ok"})

#TODO: Clean route code
@app.post("/deploy")
async def deploy_database(
    request: DeployRequest,
    #image_file: Optional[UploadFile] = File(None)
):
    
    
    if request.connection.ip:
        return JSONResponse(status_code=400, content={"message": "'ip' parameter can not be specified"})
    
    if request.connection.external != False:
        return JSONResponse(status_code=400, content={"message": "'external' parameter can not be True"})
    
    logger.info(f"Deploy request received with id '{request.id}' and manager '{request.connection.manager}'")
    
    if request.connection.manager not in SUPPORTED_MANAGERS:
        return JSONResponse(status_code=400, content={"message": f"Manager '{request.connection.manager}' not supported",
                                                      "managers": SUPPORTED_MANAGERS})
        
    ############################! Container deploynment ############################
    
    docker_client = docker.DockerClient(base_url=f"unix:/{DOCKER_SOCK}")
    
    container_image = None
    container_port = None

    if request.connection.manager == "mongodb": 
        container_image= "mongo:latest"
        container_port = "27017/tcp"
    else:
        return JSONResponse(status_code=400, content={"message": f"Manager '{request.connection.manager}' not supported",
                                                      "managers": SUPPORTED_MANAGERS})
    container = None
    try:
        
        existing_containers = docker_client.containers.list(all=True)
        
        for c in existing_containers:
            if request.id in c.name or request.id == c.name:
                return JSONResponse(
                    status_code=400,
                    content={"message": f"A container with name '{request.id}' already exists, rename the id"}
                )
        
        container = docker_client.containers.run(
            image=container_image,
            name=request.id,
            detach=True,
            ports={container_port: request.connection.port},
            network=NETWORK_NAME,
        )
        
        container.reload()
    
        if container.status != "running":
            logs = container.logs().decode()
            raise RuntimeError(f"Database created but failed to start. Logs:\n{logs}")
        
        logger.info(f"Database '{request.id}' started successfully")
    
        ############################! Database connection verification ############################
        logger.info(f"Verifying database '{request.id}' connection...")
        
        attempt = 0
        retries = 60
        while True and attempt < retries:
            attempt += 1
            try:
                if request.connection.manager == "mongodb": 
                    client = MongoClient(request.id, 27017)
                    client.admin.command("ping")
                    client.close()
                    break
                else:
                    return JSONResponse(status_code=400, content={"message": f"Manager '{request.connection.manager}' not supported",                                           "managers": SUPPORTED_MANAGERS})
            except Exception as e:
                if attempt >= retries:
                    raise RuntimeError(f"Database '{request.id}' deployed but can not be reached")
                
                logger.info(f"Attempt {attempt}: Database '{request.id}' not ready yet, retrying in 2 seconds...")
                await asyncio.sleep(2)             
        
        logger.info(f"Database '{request.id}' is ready")
        ############################! Database indexing ############################
        logger.info(f"Indexing database '{request.id}'...")
        
        index_data = {
            "id": request.id,
            "tags": request.tags,
            "connection": {
                "manager": request.connection.manager,
                "ip": request.id,
                "port": request.connection.port,
                "external": False        
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{PROXIER_ADDRESS}/indexer/index", json=index_data)
            
            if response.status_code == 400:
                logger.error(f"Bad request indexing database")
                raise RuntimeError(f"Server error indexing database: {response.json()}")
            elif response.status_code != 200:
                raise RuntimeError(f"Server error indexing database: {response.text}")
    except Exception as e:
        logger.error(f"Deployment error for database '{request.id}': {e}")
     
        if container is not None:
            try:
                container.remove(force=True)
                logger.info(f"Container '{request.id}' removed due to failure")
            except docker.errors.NotFound:
                logger.warning(f"Container '{request.id}' not found during cleanup")
            except Exception as cleanup_err:
                logger.error(f"Failed to cleanup container '{request.id}': {cleanup_err}")
        else:
            try:
                c = docker_client.containers.get(request.id)
                c.remove(force=True)
                logger.info(f"Container '{request.id}' removed by name during failure cleanup")
            except docker.errors.NotFound:
                logger.warning(f"Container '{request.id}' not found by name during cleanup")
            except Exception as cleanup_err:
                logger.error(f"Failed to cleanup container '{request.id}': {cleanup_err}")

        return JSONResponse(status_code=500, content={"message": f"Deployment aborted: {e}"})
        
    logger.info(f"Database '{request.id}' ready an indexed")
    
    return JSONResponse(
        status_code=200,
        content={"message": f"Database '{request.id}' is indexed and ready"}
    )

@app.post("/delete")
async def delete_database(request: DeleteRequest):
    docker_client = docker.DockerClient(base_url=f"unix:/{DOCKER_SOCK}")
    
    async with httpx.AsyncClient() as client:
            response = await client.post(f"{PROXIER_ADDRESS}/indexer/delete", json=request.model_dump())
            if response.status_code != 200:
                return JSONResponse(status_code=response.status_code, content=response.json())
    
    try:
        container = docker_client.containers.get(request.id)
        container.remove(force=True)
        logger.info(f"Container '{request.id}' deleted successfully")
        return JSONResponse(
            status_code=200,
            content={"message": f"Database '{request.id}' deleted successfully"}
        )
    except docker.errors.NotFound:
        logger.warning(f"Container '{request.id}' not found")
        return JSONResponse(
            status_code=404,
            content={"message": f"Container '{request.id}' not found"}
        )
    except docker.errors.APIError as e:
        logger.error(f"Docker API error while deleting '{request.id}': {e.explanation}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Docker API error: {e.explanation}"}
        )
    except Exception as e:
        logger.error(f"Unexpected error while deleting '{request.id}': {e}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Unexpected error: {e}"}
        )
           
        
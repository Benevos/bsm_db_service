
# About the project

This project implements a service to centrally manage databases through a lightweight form of Infrastructure as Code *(IaaC)* based on domain specific directives, providing the following main capabilities:  

- **Indexing**: Register existing databases using technical information and tags.  
- **Searching**: Locate indexed databases by `id` (unique result) or by `tags` (multiple results).  
- **Deployment**: Create and run new databases on demand within a Docker context, automatically registering them in the index.  
- **Deletion**: Remove databases from the index and, if internal, also delete their associated container.  

Additionally, the service is designed with a decoupled architecture to keep specialized modules (access, indexing, searching, and deployment), and future support is planned for external databases on public domains.  

## Table of contents

The next table shows the contents of this repository:

- [About the project](#about-the-project)
  - [Table of contents](#table-of-contents)
- [Service components](#service-components)
- [Default enviromental variables](#default-enviromental-variables)
- [How to use consume the service](#how-to-use-consume-the-service)
  - [Operations](#operations)
    - [Indexing](#indexing)
    - [Searching](#searching)
    - [Deployment](#deployment)
    - [Deletion](#deletion)
- [How to run](#how-to-run)
  - [Prerequisites](#prerequisites)
  - [Short answer](#short-answer)
  - [Long asnwer](#long-asnwer)


# Service components

The next list describes the functionalities of each component of the service:

- `accessor`: Point of access of the whole service, it interprets an schema in order to send it to the correspondent component that must process the request.
- `proxier`: An access point that redirects to `indexer` or `searcher` depending on the request, its only purpouse is to avoid *spaghetti coupling*.
- `indexer`: Takes an schema of descriptive and technical information of a database (whether if it exists on an external domain or in the local docker context) and indexes it to the database index.
- `searcher`: Searches for indexed databases, matching them by **id** (unique result) or **tags** (multiple results).
- `deployer`: Takes an schema of descriptive and technical information of a database and deploys it on the local docker context, then indexing it through the `indexer`.
- `dbindex`: a database that stores the information of the indexed databases.

![coupling_architecture][coupling]

[coupling]: ./assets/coupling.png


# Default enviromental variables

This section shows default enviromental variables values for each component:

*Note: Every components has an `ON_CONTAINER` boolean enviromental variable, `True` on default, if `False`, the component will search for an `ENV` file on the root directory of the app, this was done this way in the case of someone wanted this service to run without containers, but it is not tested.*

**Accessor**:
```python
PROXIER_IP = "proxier"
PROXIER_PORT = 45000
DEPLOYER_IP = "deployer"
DEPLOYER_PORT = 48000"
```
**Proxier**: 
```python
DBINDEX_IP = "dbindex"
DBINDEX_PORT = 27017
SEARCHER_IP = "searcher"
SEARCHER_PORT = 46000
DBINDEX_DB_NAME = "dbindex"
DBINDEX_COLLECTION_NAME = "databases"
```
**Searcher**: 

```python
DBINDEX_IP = "dbindex"
DBINDEX_PORT = 27017
DBINDEX_DB_NAME = "dbindex"
DBINDEX_COLLECTION_NAME = "databases"
```
**Indexer**: 
```python
DBINDEX_IP = "dbindex"
DBINDEX_PORT = 27017
SEARCHER_IP = "searcher"
SEARCHER_PORT = 46000
DBINDEX_DB_NAME = "dbindex"
DBINDEX_COLLECTION_NAME = "databases"
```
**Deployer**:

```python
PROXIER_IP = "proxier"
PROXIER_PORT = 45000
NETWORK_NAME = "bsm_db_service"
DOCKER_SOCK = "/var/run/docker.sock"
```

# How to use consume the service

Once the service is deployed and active you need to follow a *schema* depending on the operation you want to do.

All the request need to be sent to this route: 

`[ACCESSOR_IP]:[ACCESSOR_PORT]/operation`

For example:




## Operations

In the next topics, there are described the available operations and the required schemas for each one.

*Note: Schemas have values with the format `[description: type]`, that are meant to be replaced with the actual values with the data types described.*

### Indexing

This operation takes an *schema* of descriptive and technical information of a database (whether if it exists on an external domain or in the local docker context) and indexes it to the database index.

**Schema:**

```python
{
    "operation": "deploy",
    "parameters": {
        "id": [database_id: str]
        "tags": [values: dict[str, any]],
        "connection": {
            "manager": [database_manager: str],
            "ip": [database_ip: str],
            "port:": [database_port: int],
            "external" [bool]
        }
    }
}
```

*Note: Indexing `external: True` (external domain databases) is not supported yet since external databases are typically not exposed to public internet and they need to be accessed by private APIs.*

### Searching

Searches for indexed databases, matching them by **id** (unique result) or **tags** (multiple results). 


**ID schema:**
```python
{
    "operation": "search",
    "parameters": {
        "id": [database_id: str]
    }
}
```

**Tags schema:**
```python
{
    "operation": "search",
    "parameters": {
        "tags": [values: dict[str, any]]
    }
}
```

`[values: dict[str, any]]` can be a simple `dict` format or a `mongodb` query format, allowing to execute query logic.

### Deployment

This operation deploys a new database as a container with the user specifications within the docker context the service exists.


**Schema:**
```python
{
    "operation": "deploy",
    "parameters": {
        "id": [database_id: str]
        "tags": [values: dict[str, any]],
        "connection": {
            "manager": [database_manager: str],
            "port:": [database_port: int],
        }
    }
}
```

*Note: Currently the only value supported for `manager` in deployment operation is `"mongodb"`*.

### Deletion

This operation deletes indexed databases whether internal or external managed. If the database is internal, `accessor` will send the request to `deployer` and it will delete the container associated wiht the request, then `indexer` will unindex it. If the database is external, `accessor` will send the request to `indexer` (trough `proxier`) and just delete the registry.

**Schema:**
```python
{
    "operation": "delete",
    "parameters": {
        "id": [database_id: str]
    }
}
```

# How to run

This sections introduces information to deploy and run the service

## Prerequisites

The next requirements must be met before running the service:

- `docker` installed
- unix enviroment (`wsl` or `linux` distro)

## Short answer

Follow the next steps to run the service:

1. Download this repository and extract it.

```bash
git clone https://github.com/Benevos/bsm_db_service.git
```

2. `cd` into the repo folder.

```
cd bsm_db_service
```

3. Run the next command on terminal: 

```bash
./run.sh
```
Done.

## Long asnwer

In case you need a custom implementation of the service, follow the next steps:

1. Start by dowloading this repo.

```bash
git clone https://github.com/Benevos/bsm_db_service.git.git
```
2. `cd` into the repository folder.

```
cd bsm_db_service
```

3. Check for the enviromental variables you can choose in [Default enviromental variables](#default-enviromental-variables), and do the changes on the `compose.yml` file.

4. Edit the `run.sh` file on the `NETWORK_NAME` if you want a different docker network name for the service.

```bash
NETWORK_NAME="bsm_db_service" # <-- Change it for custom name
```

5. If you changed the `NETWORK_NAME` you need to specify in the enviromental variables of the services that need it as listed above in the section [Default enviromental variables](#default-enviromental-variables) on the `compose.yml` file.

6. Run the next command on terminal: 

```bash
./run.sh
```
That's it, the service must be running now!






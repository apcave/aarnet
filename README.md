# Aarnet
Backend Network Software Engineering Assessment
## Network Topology Tracing

### Package Features
#### Initial Repurposed
This repo started code repurposed from a Django course. It had the following features:
* Django API
* uwsgi - micro web server for deployment
* PostGresSQL - client code for remote database
* Stateless Application, the code was developed for deployment in a docker container.

#### Current Package Features
* SQLite, db local file for persistent storage.
* Not stateless will not work in docker container.


## Setup and Test
To setup the DJANGO environment locally.
On mac OS run:
```bash
./setup
./run
open "http://localhost:8000/api/docs"
```



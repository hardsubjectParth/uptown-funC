# uptown-funC
SIH-2026 submission

start : ```podman compose up```

Or rebuild/pull : `podman compose up -d`

check : `podman ps`

Test vLLM : `curl http://localhost:8000/v1/models`

test postgreSQL : ``` 
podman exec -it <postgres-container-name> \
  psql -U rag -d rag ```

### RUNNING 
`python -m venv func`

`func\Scripts\activate`



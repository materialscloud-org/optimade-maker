## how to start a mongodb container

```
docker run \
    --detach \
    --name mongo \       
    --volume mongodb-persist-optimade-local:/data/db \
    --network optimade \
    -p 27017:27017 \             
    mongo:4   
```

## how to start an optimade server using the start mongodb container

```
docker run \
    --rm \    
    --publish 8081:5000 \
    --env MAIN=main \                                 
    --name mc-archive-optimade \   
    --network optimade \
    --env OPTIMADE_CONFIG_FILE= \
    --env optimade_insert_test_data=false \
    --env optimade_database_backend=mongodb \
    --env optimade_mongo_uri=mongodb://mongo:27017 \
    --env optimade_mongo_database=mc_optimade \         
    --env optimade_structures_collection=structures \
    --env optimade_page_limit=25 \
    --env optimade_page_limit_max=100 \
    --env optimade_base_url=http://localhost:8081 \
    --env optimade_index_base_url=http://localhost:8080 \
    --env optimade_provider="{\"prefix\":\"myorg\",\"name\":\"My Organization\",\"description\":\"Short description for My Organization\",\"homepage\":\"https://example.org\"}" \
    ghcr.io/materials-consortia/optimade:latest
```

start another server using new collection (notice, the port is mapped to `8082`)

```
docker run \
    --rm \    
    --publish 8082:5000 \
    --env MAIN=main \                                 
    --name mc-archive-optimade \
    --network optimade \
    --env OPTIMADE_CONFIG_FILE= \
    --env optimade_insert_test_data=false \
    --env optimade_database_backend=mongodb \
    --env optimade_mongo_uri=mongodb://mongo:27017 \
    --env optimade_mongo_database=mc_optimade_index_00 \
    --env optimade_structures_collection=structures \
    --env optimade_page_limit=25 \
    --env optimade_page_limit_max=100 \
    --env optimade_base_url=http://localhost:8082 \
    --env optimade_index_base_url=http://localhost:8080 \
    --env optimade_provider="{\"prefix\":\"myorg\",\"name\":\"My Organization\",\"description\":\"Short description for My Organization\",\"homepage\":\"https://example.org\"}" \
    ghcr.io/materials-consortia/optimade:latest
```

run data inject script:

```bash
cd mc_optimade/src/jsonl_server
python load_data.py mc_optimade_index_00 optimade.jsonl
```

first arg is the collection name, second arg is the input jsonl file.
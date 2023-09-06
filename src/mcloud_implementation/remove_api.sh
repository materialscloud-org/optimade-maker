#!/usr/bin/env bash


docker stop optimade_$1
docker rm optimade_$1

optimade-launch profile remove $1

docker exec -it ubuntu_mongo_1 mongosh optimade_$1 --eval "db.dropDatabase()"

sudo unlink /home/ubuntu/optimade-sockets/$1.sock

# update the index and landing page
./mcloud_master.py --skip_download --skip_convert --skip_mongo_inject --skip_containers

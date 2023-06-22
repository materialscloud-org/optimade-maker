#!/usr/bin/env bash


docker stop optimade_$1
docker rm optimade_$1

optimade-launch profile remove $1

docker exec -it ubuntu_mongo_1 mongo $1 --eval "db.dropDatabase()"

sudo unlink /home/ubuntu/optimade-sockets/$1.sock 


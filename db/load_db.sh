#!/bin/bash

docker cp ./derpibooru_reduced.pgdump caption-db:/derpibooru_reduced.pgdump && \
	docker exec caption-db dropdb --if-exists derpibooru && \
  docker exec caption-db createdb derpibooru &&  \
	docker exec caption-db pg_restore -O -d derpibooru /derpibooru_reduced.pgdump


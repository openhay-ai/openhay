#!/bin/bash

set -e
set -u

function create() {
	local database=$1
	echo "Database creation '$database'"
	psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
	    CREATE USER $database;
	    CREATE DATABASE $database;
	    GRANT ALL PRIVILEGES ON DATABASE $database TO $database;
EOSQL
}

if [ -n "$POSTGRES_DATABASES" ]; then
	echo "Databases creation: $POSTGRES_DATABASES"
	for db in $(echo "$POSTGRES_DATABASES" | tr ',' ' '); do
		create "$db"
	done
	echo "Multiple databases created"
fi
Start the containers:

```
docker-compose up --build
```

Load data to Virtuoso:

```
docker exec -i virt-db isql 1111 dba secret load-data.sql
```

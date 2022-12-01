# cookie thing

two options to run

## unsafe development and so on
#### this will not work without postgresql db installed outside
```bash
cd app
uwsgi --ini uwsgi.ini
```

## docker
1. Replace all `REPALCE_ME` constants in docker-compose.example.yml
2. rename it to `docker-compose.yml`
3. 
```bash
docker-compose build
docker-compose up -d
```

## after running
access the site at http://localhost:5000 

it will also be fully exposed to the internet at `<your-ip>:5000`.

outputs will go to postgresql db somehow

backup system is outside of the scope of this repo

## bugs
literally millions of them. good luck

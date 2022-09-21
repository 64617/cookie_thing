# cookie thing

two options to run

## unsafe development and so on
```bash
cd app
uwsgi --ini uwsgi.ini
```
## docker
In `docker-compose.yml`, replace 
```
device: /REPLACE_ME/PATH/TO/output_descriptions
```
with wherever you want the image descriptions to be stored. Then run:
```bash
docker-compose build
docker-compose up -d
```

## after running
access the site at http://localhost:5000 

it will also be fully exposed to the internet at `<your-ip>:5000`.

outputs will be written to `output_descriptions/`, which will be in the `app/` folder if you run without docker.

Example contents:
```bash
$ tree ../output_descriptions
../output_descriptions
...
├── 61
│   ├── 0.txt
│   └── 1.txt
...
```

## bugs
literally millions of them. good luck

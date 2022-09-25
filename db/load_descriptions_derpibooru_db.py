
import psycopg
import os
import time
import pathlib
class Timer:
    def __enter__(self): self.start = time.time()
    def __exit__(self, *_): print((time.time()-self.start))

# Database connection configuration and default values
POSTGRES_DATABASE = os.environ.get("POSTGRES_DATABASE", "derpibooru")
POSTGRES_USERNAME = os.environ.get("POSTGRES_USERNAME", "derpibooru_user")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")


# Collect captions{} from original storage folder
DESC_DIR = pathlib.Path('~/output_descriptions/')
captions = {} # Dict[id: int, caption: str]
with open('../app/image_ids.txt') as f:
    for id_s in f.read().split('\n'):
        p = DESC_DIR.joinpath(id_s, '0.txt')
        if p.exists():
            cap = p.read_text()
            captions[int(id_s)] = {
                'ip_hash': None,
                'session_id': None,
                'image_id': int(id_s),
                'prompt_text': cap,
            }

# get IP hash / Session ID data from blame.log
for log in DESC_DIR.joinpath('blame.log').read_text().split('\n'):
    if not log: continue
    # 272261/0.txt -- b8dc6bee-a69f-4811-8223-0635c5421ce6 -- 07e2859b97bd65753503fe40624141240fc4ca2e460fb79f87b5b9c2f5e233e4
    fname, session_id, *ip_hash = log.split(' -- ')
    idx = int(fname.split('/')[0])
    captions[idx]['session_id'] = session_id
    if ip_hash:
        captions[idx]['ip_hash'] = ip_hash[0]


# Build the postgres database connection string
connection_string = f"dbname={POSTGRES_DATABASE} user={POSTGRES_USERNAME}"
if POSTGRES_PASSWORD is not None:
    connection_string += f" password={POSTGRES_PASSWORD}"

# Connect to the database
with psycopg.connect(connection_string) as conn:
    # Open a cursor to perform database operations
    with conn.cursor() as cur:
        # Create table & data. We start a transaction so that all operations are atomic
        # (and we won't be left with a half-culled database if the operation fails).
        with conn.transaction():
            sql = '''
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = 'image_prompts'
            '''
            if cur.execute(sql).fetchone() is not None: # table exists
                if 'y' != input("DO YOU WANT TO DROP THE image_prompts TABLE, DELETING ITS DATA? (y/n) "):
                    print('not deleting, exiting.')
                    exit()
                sql = 'DROP table image_prompts'
                cur.execute(sql)

            # create table
            sql = '''
                CREATE TABLE public.image_prompts (
                  ip_hash text,
                  session_id text,
                  prompt_text text NOT NULL,
                  prompt_id integer NOT NULL,
                  image_id integer REFERENCES public.images (id) NOT NULL,
                  PRIMARY KEY (image_id, prompt_id)
                )
            '''
            cur.execute(sql)

            # create indexes on table
            sql = '''
                CREATE INDEX ip_image_mm_idx
                ON image_prompts (ip_hash, image_id);
                CREATE INDEX session_image_mm_idx
                ON image_prompts (session_id, image_id);
            '''
            cur.execute(sql)

            # add data to table 
            with cur.copy('COPY image_prompts (ip_hash, session_id, image_id, prompt_text, prompt_id) FROM STDIN') as copy:
                for record in captions.values():
                    copy.write_row((*record.values(), 0))

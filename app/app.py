import pathlib
import psycopg
import time
import uuid
import os
import json
from subprocess import check_call
from threading import Timer
from hashlib import pbkdf2_hmac
from collections import defaultdict, deque
from flask import Flask,render_template,request,redirect,send_file,session,make_response
from tqdm import tqdm
from typing import List,Set,Tuple

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ["FLASK_SECRET_KEY"] #NOTE: IF YOU EVER MAKE CHANGES TO THE SESSION HANDLING CODE, YOU NEED TO CHANGE THIS (or purge all sessions somehow otherwise)
app.config['MAX_CONTENT_LENGTH'] = 1024*1024

PBKDF2_ITERS = 50000
IP_SALT = bytes.fromhex(os.environ["IP_SALT"])
assert len(IP_SALT) == 16
def ip_hash(ip: str):
    return pbkdf2_hmac('sha256', ip.encode(), IP_SALT, PBKDF2_ITERS).hex()

# Connect to the database
DB_CONN = psycopg.connect(
    host = 'caption-db',
    port = 5432,
    dbname   = os.environ.get("POSTGRES_DATABASE", "derpibooru"),
    user     = os.environ.get("POSTGRES_USERNAME", "derpibooru_user"),
    password = os.environ["POSTGRES_PASSWORD"],
    autocommit=True
)

def add_cursor(f):
    def inner(self, *args, **kwargs):
        with DB_CONN.cursor() as cur:
            return f(self, cur, *args, **kwargs)
    return inner

with DB_CONN.cursor() as cur:
    res = cur.execute('''SELECT COUNT(id) FROM images''')
    REQUIRED = res.fetchone()[0]*2 # pyright: ignore

class DurationOf:
    def __init__(self, title: str): self.s = title
    def __enter__(self): self.start = time.time()
    def __exit__(self, *_):
        delta = time.time()-self.start
        print(f'{self.s} -- took {delta} seconds')

class ImageQueue:
    def __init__(self):
        self.cached_ids = defaultdict(deque)
        self.cached_filters = defaultdict(str)
        self.cached_progress = (time.time(), self.get_progress())

    def progress_str(self) -> str:
        '''
        if time.time()-self.cached_progress[0] > 300:
            self.cached_progress = (time.time(), self.get_progress())
        return f'{self.cached_progress[1]:.9%}'
        '''
        return f'{self.get_progress():.9%}'

    @add_cursor
    def get_progress(self, cur=...) -> float:
        '''query the DB for how close we are to reaching
        2 captions per image'''
        with DurationOf('get_progress()'):
            sql = '''
                SELECT COUNT(image_id) FROM image_prompts
                WHERE prompt_id = ANY(ARRAY[0,1])
            '''
            complete = cur.execute(sql).fetchone()[0] # pyright: ignore
        return complete/REQUIRED

    @add_cursor
    def write_desc(self, cur, idx: int, desc: str, uid: str, ip: str):
        # use a transaction to ensure atomic prompt_id counting
        with DB_CONN.transaction():
            # get number of prompts so far
            res = cur.execute('''
                SELECT COUNT(prompt_id) FROM image_prompts
                WHERE image_id = %s
            ''', (idx,))
            new_pid = res.fetchone()[0] # pyright: ignore

            # add new prompt
            res = cur.execute('''
                INSERT INTO image_prompts
                (ip_hash, session_id, image_id, prompt_text, prompt_id)
                VALUES (%s,%s,%s,%s,%s)
            ''', (ip_hash(ip), uid, idx, desc, new_pid))

    def get_next(self, session: str, superlist: str, whitelist: str, blacklist: str):
        print('TODO:', superlist)
        expected_filter = whitelist+blacklist
        # if a user changed their filter, delete their image cache.
        if self.cached_filters[session] != expected_filter:
            self.cached_ids[session] = deque()
            self.cached_filters[session] = expected_filter

        # if the user image cache is about to run out, replenish it
        cache = self.cached_ids[session]
        if len(cache) < 2:
            with DurationOf('fill_cache()'):
                self.fill_cache(session, whitelist, blacklist) # pyright: ignore
                print(cache)
        
        # pop from cache
        if not cache: return None
        return cache.popleft()
    @add_cursor
    def fill_cache(self, cur, session: str, whitelist: str, blacklist: str, random_threshold: float=0.05):
        '''Adds 100 images to the image cache for user `session`'''
        QUERY_LIMIT = 100

        # SQL SELECT query with 6 parts:
        sql = 'WITH'

        # 0. predefine variables (blacklist)
        if blacklist:
            sql += '''
            bl as (
              SELECT id FROM tags
              WHERE name = ANY(%s)
            ),
            '''

        # 1. Begin query on image_taggings table for distinct image_ids
        sql += '''
            possible_ids as (
                SELECT DISTINCT ON (image_id) image_id FROM image_taggings
        '''

        # 2. filter for tags in whitelist
        if whitelist:
            sql += '''
                WHERE tag_id IN (
                  SELECT id from tags
                    WHERE name = ANY(%s)
                )
            '''

        # 3. filter against images that have prompts already
        # TODO: figure out when to start filtering against prompt_id > 0
        word = 'AND' if whitelist or blacklist else 'WHERE'
        sql += f'''
                {word} image_id NOT IN (
                  SELECT image_id FROM image_prompts
                )
            )
        '''

        # 4. filter against tags from blacklist
        # this entire query is basically a waste of time if there's no blacklist.
        sql += '''
            SELECT image_id from image_taggings
            WHERE image_id IN (
              SELECT image_id FROM possible_ids
            )
            GROUP BY image_id
        '''
        if blacklist: sql += '''
            HAVING bool_and(tag_id NOT IN (
              SELECT id FROM bl
            ))
            '''
        else: sql += '''
            HAVING TRUE
        '''

        # 5. get the first 100 images randomly from that query.
        # TODO: alt-path for when the database "runs out" and returns < QUERY_LIMIT entries
        sql += f'''
            ORDER BY random() < {random_threshold} LIMIT {QUERY_LIMIT}
        '''
        # execute query
        print(f'{whitelist=},{blacklist=}')
        print(sql)
        res = cur.execute(sql, tuple(
            ls.split(',')
            for ls in (blacklist, whitelist)
            if ls
        ))
        # add result to cached ID list
        self.cached_ids[session].extend(
            (t[0] for t in res.fetchall())
        )

iq = ImageQueue()

DEFAULT_FILTERS = {
    'any': ('', '', ''),
    'NSFW': ('', 'questionable,explicit', ''),
    'NSFL': ('', 'grimdark,semi-grimdark', 'safe'),
    'SAFE': ('', 'safe,suggestive', ''),
    'PONY': ('', 'pony', 'eqg,human,anthro')
}

@app.route("/")
def index():
    # handle sessions
    if 'uid' not in session: # There is nothing stopping someone from clearing cookies and spawning more sessions. 
        session['uid'] = uuid.uuid4()

    # get whitelist/blacklist from cookies
    typ = request.cookies.get("image_filter", "any")
    if typ == 'custom':
        superlist = request.cookies.get("superlist", "")
        whitelist = request.cookies.get("whitelist", "")
        blacklist = request.cookies.get("blacklist", "")
    else:
        superlist,whitelist,blacklist = DEFAULT_FILTERS[typ]
    
    # return front page with image
    idx = iq.get_next(str(session), superlist, whitelist, blacklist)
    if idx is None:
        resp = make_response('Could not find any images matching your query. (possible bug?)', 500)
        resp.delete_cookie('superlist')
        resp.delete_cookie('whitelist')
        resp.delete_cookie('blacklist')
        return resp
    return render_template('index.html', derpi_id=idx,
       progress=iq.progress_str())

@app.route('/api/submit', methods=['POST'])
def submit():
    # sessions are cryptographically signed and should not be editable
    uid = session.get('uid', None)
    if uid is None:
        return 'SESSION MISSING', 403 
    ip = request.headers['Cf-Connecting-Ip']
    #
    idx,desc,ts = int(request.form['idx']), request.form['desc'],int(request.form['timestamp'])
    if time.time()-ts > 60*59:
        return 'FORM EXPIRED',500
    if not desc or len(desc) > 1000:
        return 'RESPONSE TOO SHORT / LONG', 500
    iq.write_desc(idx, desc, uid, ip) # pyright: ignore
    return redirect('/', code=302)

BACKUP_DIR = pathlib.Path('/backups/')
BACKUP_DIR.mkdir(exist_ok=True)
BACKUP_FILE = BACKUP_DIR.joinpath('captions-latest.json')

@app.route('/super/secret/endpoint')
def super_secret_endpoint():
    return send_file(str(BACKUP_FILE), as_attachment=True)

def create_backup():
    # call this recursively every 6 hours
    Timer(60*60*6, create_backup).start()
    # create JSON dump cache
    with DB_CONN.cursor() as cur, DurationOf("JSON dump"):
        res = cur.execute('SELECT * FROM image_prompts')
        captions = [
            dict(zip(
                ('ip_hash', 'session_id', 'prompt_text', 'prompt_id', 'image_id'),
                row,
            )) for row in res.fetchall()
        ]
        with BACKUP_FILE.open('w') as f:
            json.dump(captions,f)
create_backup()

# note: these json backups are provided for mere conveinence.
# Actual backup process exists to store pg_dump outputs every x hours.


if __name__ == '__main__':
    app.debug = True;
    app.run(debug=True, threaded=True, host='0.0.0.0', port=5000)

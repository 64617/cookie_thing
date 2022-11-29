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
from flask import Flask,render_template,request,redirect,send_file,session,make_response,jsonify,redirect,url_for
from tqdm import tqdm
from typing import List,Set,Tuple,Optional

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
    host = os.environ.get("DB_CONTAINER", 'caption-db'),
    port = 5432,
    dbname   = os.environ.get("POSTGRES_DATABASE", "derpibooru"),
    user     = os.environ.get("POSTGRES_USERNAME", "derpibooru_user"),
    password = os.environ["POSTGRES_PASSWORD"],
    autocommit=True
)

def add_cursor_noself(f):
    def inner(*args, **kwargs):
        with DB_CONN.cursor() as cur:
            return f(cur, *args, **kwargs)
    return inner
def add_cursor(f):
    def inner(self, *args, **kwargs):
        with DB_CONN.cursor() as cur:
            return f(self, cur, *args, **kwargs)
    return inner

with DB_CONN.cursor() as cur:
    # get total number of images
    res = cur.execute('''SELECT COUNT(id) FROM images''')
    REQUIRED = res.fetchone()[0]*2 # pyright: ignore

    # Create a helper function in SQL to convert tag names to tag ids
    cur.execute('''
        CREATE OR REPLACE FUNCTION tag_name_to_id (tag_name TEXT) RETURNS BIGINT AS $$
          DECLARE tag_id BIGINT;
          BEGIN
            SELECT id INTO tag_id FROM tags
            WHERE name = tag_name;
            RETURN tag_id;
          END;
        $$ LANGUAGE plpgsql;
    ''')

    # Create a prepared statement for JSON dumping. Hotfix for a bug.
    cur.execute('''
        PREPARE jsondumpplan AS
          SELECT * FROM image_prompts
    ''')


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
        print(f'Log /api/submit - {uid=} {ip=} {idx=}')
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
        print(f'{session=}, {superlist=}, {whitelist=}, {blacklist=}')
        expected_filter = superlist+whitelist+blacklist
        # if a user changed their filter, delete their image cache.
        if self.cached_filters[session] != expected_filter:
            self.cached_ids[session] = deque()
            self.cached_filters[session] = expected_filter

        # if the user image cache is about to run out, replenish it
        cache = self.cached_ids[session]
        if len(cache) < 2:
            with DurationOf('fill_cache()'):
                self.fill_cache(session, superlist, whitelist, blacklist) # pyright: ignore
                print(cache)

        # pop from cache
        if not cache: return None
        return cache.popleft()
    @add_cursor
    def filtered_query(
        self, cur,
        superlist: str, whitelist: str, blacklist: str,
        QUERY_LIMIT: int=100, ip_filter: Optional[str]=None, unprompted: bool=True
    ):
        '''Queries the database (randomly) for images based on the given filters,
        returning QUERY_LIMIT image IDs.'''

        # convert stringified tag lists to actual lists
        slist,wlist,blist = [
            [] if not s else s.split(',')
            for s in (superlist,whitelist,blacklist)
        ]

        # extract tag_name:tag_id pairs with a DB query
        tags_used = set([*slist,*wlist,*blist])
        # this doesn't need a transaction because the tags table should not change.
        res = cur.execute('''
            SELECT id, name FROM tags
            WHERE name = ANY(%s)
        ''', (list(tags_used),))
        tag_name_to_id = {name:tag_id for tag_id,name in res.fetchall()}
        # check for missing tags
        if len(tag_name_to_id) != len(tags_used):
            raise RuntimeError(f"The following tags were not found: {tags_used - set(tag_name_to_id)}")
        def to_tag_ids(tag_names: List[str]):
            return [tag_name_to_id[w] for w in tag_names]

        sql = self.filtered_query_build(slist, wlist, blist, QUERY_LIMIT, ip_filter, unprompted)
        print(sql)
        #
        args = to_tag_ids(slist)
        if ip_filter: args.append(ip_filter)
        if wlist: args.append(to_tag_ids(wlist))
        if blist: args.append(to_tag_ids(blist))
        print(args)
        res = cur.execute(sql, args)
        return (t[0] for t in res.fetchall())


    def filtered_query_build(self, slist: List[str], wlist: List[str], blist: List[str], QUERY_LIMIT: int, ip_filter: Optional[str], unprompted: bool):
        # Multi step SQL query.
        # 0. selecting image_ids from image_taggings,
        sql = '''
          SELECT image_id FROM (
            SELECT it.image_id FROM image_taggings it
        '''

        # 1. do an inner join with all entries in slist + once for whitelist,
        for i in range(len(slist)+bool(wlist)):
            sql += f'INNER JOIN image_taggings it{i} on it{i}.image_id = it.image_id\n'

        # 2. filter against images already prompted
        # TODO: allow for images with caption count < x
        subquery = '''
              SELECT image_id FROM image_prompts
              WHERE ip_hash = %s
        ''' if ip_filter else '''
              SELECT image_id FROM image_prompts
        '''
        sql += f'''
            WHERE it.image_id {'NOT ' if unprompted else ''}IN ({subquery})
        '''

        # 3. filter for all tags in superist, and any tag in whitelist
        # note: for simplicity of programming we don't use `it` (the original) here
        for i in range(len(slist)):
            sql += f'AND it{i}.tag_id = %s\n'
        if wlist:
            sql += f'AND it{len(slist)}.tag_id = ANY(%s)\n'

        # 4. filter against blacklist tags, and also limit query output to unique image_id
        sql += 'GROUP BY it.image_id\n'
        sql += 'HAVING every(it.tag_id != ALL(%s))\n' \
            if blist else 'HAVING TRUE\n'

        # 5. get query entries randomly.
        # TODO: unfortunately this will do a full table scan (very slow). fixme
        sql += f'''
          ) t
          ORDER BY random() LIMIT {QUERY_LIMIT}
        '''
        return sql

    def fill_cache(self, session: str, superlist: str, whitelist: str, blacklist: str):
        '''Adds 100 images to the image cache for user `session`'''
        print(f'{superlist=}, {whitelist=}, {blacklist=}')

        # add result to cached ID list
        id_gen = self.filtered_query(superlist, whitelist, blacklist) # pyright: ignore
        self.cached_ids[session].extend(id_gen)

iq = ImageQueue()

DEFAULT_FILTERS = {
    'any': ('', '', ''),
    'NSFW': ('', 'questionable,explicit', ''),
    'NSFL': ('', 'grimdark,semi-grimdark', 'safe'),
    'SAFE': ('', 'safe,suggestive', ''),
    'PONY': ('', 'pony', 'eqg,human,anthro')
}

def find_filters(cookies) -> Tuple[str,str,str]:
    # get whitelist/blacklist from cookies
    typ = cookies.get("image_filter", "SAFE")
    if typ == 'custom':
        superlist = cookies.get("superlist", "")
        whitelist = cookies.get("whitelist", "")
        blacklist = cookies.get("blacklist", "")
    else:
        superlist,whitelist,blacklist = DEFAULT_FILTERS[typ]
    return superlist, whitelist, blacklist

def error_avoiding_deadlock(res: str):
    resp = make_response(res, 500)
    for cook in ['superlist', 'whitelist', 'blacklist']:
        resp.delete_cookie(cook)
    return resp

@app.route("/")
def index():
    # handle sessions
    if 'uid' not in session: # There is nothing stopping someone from clearing cookies and spawning more sessions. 
        session['uid'] = uuid.uuid4()

    superlist,whitelist,blacklist = find_filters(request.cookies)

    # return front page with image
    try:
        idx = iq.get_next(str(session), superlist, whitelist, blacklist)
    except RuntimeError as e:
        return error_avoiding_deadlock(str(e))
    if idx is None:
        return error_avoiding_deadlock('Could not find any images matching your query. (possible bug?)')

    print(f"Log / - Rendering {idx}")
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

@app.route('/api/collect/<int:use_filter>')
def collect(use_filter: int):
    ip = request.headers['Cf-Connecting-Ip']
    prompts = get_prompts_of_user(ip_hash(ip), bool(use_filter)) # pyright: ignore
    return jsonify(prompts)

@add_cursor_noself
def get_prompts_of_user(cur, ip_h: str, use_filter: bool):
    superlist,whitelist,blacklist = find_filters(request.cookies) if use_filter else ('','','')
    image_ids = iq.filtered_query(superlist, whitelist, blacklist, 99999999, ip_h, False) # pyright: ignore
    res = cur.execute('''
        SELECT image_id, prompt_text FROM image_prompts
        WHERE image_id = ANY(%s)
    ''', (list(image_ids),))
    return res.fetchall()

BACKUP_DIR = pathlib.Path('/backups/')
BACKUP_DIR.mkdir(exist_ok=True)
BACKUP_FILE = BACKUP_DIR.joinpath('captions-latest.json')

@app.route('/tokenizer')
def tokenizer():
    return redirect(url_for('static', filename='token.html'))

@app.route('/super/secret/endpoint')
def super_secret_endpoint():
    return send_file(str(BACKUP_FILE), as_attachment=True)

def create_backup():
    # call this recursively every 6 hours
    Timer(60*60*6, create_backup).start()
    # create JSON dump cache
    with DB_CONN.cursor() as cur, DurationOf("JSON dump"):
        res = cur.execute('execute jsondumpplan')
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

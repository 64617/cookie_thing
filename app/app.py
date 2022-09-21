import pathlib
import time
import uuid
from threading import Timer
from flask import Flask,render_template,request,redirect,send_file,session
from tqdm import tqdm
from heapq import heappop, heappush
from typing import List,Set,Tuple


RATINGS_DIR = pathlib.Path('content_ratings')
DESC_DIR = pathlib.Path('output_descriptions/')
if not DESC_DIR.exists():
    print("WARNING: output directory does not exist. creating it.")
    print("Be especially concerned if you are running this in docker.")
    DESC_DIR.mkdir()
BLAME_LOG = DESC_DIR.joinpath('blame.log')
BLAME_FILE = open(BLAME_LOG, 'a') # STUPID

app = Flask(__name__)
app.config['SECRET_KEY'] = 'NOTE: IF YOU' #EVER MAKE CHANGES TO THE SESSION HANDLING CODE, YOU NEED TO CHANGE THIS (or purge all sessions somehow otherwise)
app.config['MAX_CONTENT_LENGTH'] = 1024*1024


def merge_id_files_to_set(fnames: List[str]) -> Set[int]:
    s = set()
    for fname in fnames:
        with open('fname') as f:
            for w in f.readlines():
                s.add(int(w))
    return s

images_NSFW = merge_id_files_to_set([
    'explicit_image_ids.txt',
    'questionable_image_ids.txt',
])
images_NSFL = merge_id_files_to_set([
    'grimdark_image_ids.txt',
    'grotesque_image_ids.txt',
])
images_SAFE = merge_id_files_to_set([
    'semi-grimdark_image_ids.txt',
    'safe_image_ids.txt',
    'suggestive_image_ids.txt',
])


class ImageQueue:
    def __init__(self, image_ids: List[Tuple[int,int]]):
        self.nsfw, self.nsfl, self.safe = [],[],[]
        self.pq = []
        self.count_count = [0,0,0]
        self.desc_cnt = {}
        for cnt,idx in image_ids:
            heappush(self.pq, (cnt,idx))
            self.count_count[bool(cnt) + (cnt>1)] += 1 
            self.desc_cnt[idx] = cnt
        self.REQUIRED = len(self.desc_cnt)*2
    def get_next(self, typ: str="any") -> Tuple[int,int]:
        if typ == 'any':
            return heappop(self.pq)
        raise NotImplementedError
    def increment(self, idx: int) -> int:
        old_cnt = self.desc_cnt[idx]
        if old_cnt < 2:
            self.count_count[old_cnt] -= 1
            self.count_count[old_cnt+1] += 1
        self.desc_cnt[idx] += 1
        heappush(self.pq, (old_cnt+1, idx))
        return old_cnt
    def check_if_missing(self, idx: int, old_cnt: int):
        if self.desc_cnt[idx] == old_cnt:
            heappush(self.pq, (old_cnt,idx))
    def progress_str(self) -> str:
        progress = (self.count_count[1]+self.count_count[2]*2)/self.REQUIRED
        return f'{progress:.9%}'

with open('image_ids.txt') as f:
    image_ids = []
    for id_s in tqdm(f.read().split('\n'), desc="Loading/creating description folders..."):
        if not id_s: continue
        p = DESC_DIR.joinpath(id_s)
        p.mkdir(exist_ok=True)
        # i hate this
        cnt,idx = len(list(p.iterdir())), int(id_s)
        image_ids.append((cnt,idx))
    iq = ImageQueue(image_ids)

def write_desc(idx: int, desc: str, uid: str):
    p = DESC_DIR.joinpath(str(idx))
    old_cnt = iq.increment(idx)
    p.joinpath(f'{old_cnt}.txt').write_text(desc)
    BLAME_FILE.write(f'{idx}/{old_cnt}.txt -- {uid}\n')
    BLAME_FILE.flush()

@app.route("/")
def index():
    # handle sessions
    if 'uid' not in session: # There is nothing stopping someone from clearing cookies and spawning more sessions. 
        session['uid'] = uuid.uuid4()
    #
    cnt,idx = iq.get_next()
    # this is dumb code.
    t = Timer(60*60, lambda: iq.check_if_missing(idx,cnt))
    t.start()
    # end of dumb code.
    return render_template('index.html', derpi_id=idx,
       progress=iq.progress_str())

@app.route('/api/submit', methods=['POST'])
def submit():
    # sessions are cryptographically signed and should not be editable
    uid = session.get('uid', None)
    if uid is None:
        return 'SESSION MISSING', 403 
    #
    idx,desc,ts = int(request.form['idx']), request.form['desc'],int(request.form['timestamp'])
    if time.time()-ts > 60*59:
        return 'FORM EXPIRED',500
    if not desc or len(desc) > 1000:
        return 'RESPONSE TOO SHORT / LONG', 500
    write_desc(idx, desc, uid)
    return redirect('/', code=302)

@app.route('/super/secret/endpoint')
def super_secret_endpoint():
    return send_file("./output_backups/captions-latest.tar.gz")

if __name__ == '__main__':
    app.debug = True;
    app.run(debug=True, threaded=True, host='0.0.0.0', port=5000)

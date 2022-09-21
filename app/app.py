import pathlib
import time
from threading import Timer
from flask import Flask,render_template,request,redirect
from tqdm import tqdm
from heapq import heappop, heappush
pq = []
DESC_DIR = pathlib.Path('output_descriptions/')
if not DESC_DIR.exists():
    print("WARNING: output directory does not exist. creating it.")
    print("Be especially concerned if you are running this in docker.")
    DESC_DIR.mkdir()

desc_cnt = {}
count_count = [0,0,0]
with open('image_ids.txt') as f:
    for id_s in tqdm(f.read().split('\n'), desc="Loading/creating description folders..."):
        if not id_s: continue
        p = DESC_DIR.joinpath(id_s)
        p.mkdir(exist_ok=True)
        # i hate this
        cnt,idx = len(list(p.iterdir())), int(id_s)
        count_count[bool(cnt) + (cnt>1)] += 1
        heappush(pq, (cnt,idx))
        desc_cnt[idx] = cnt
REQUIRED = len(desc_cnt)*2

'''
def real_desc_count(idx: int) -> int:
    p = DESC_DIR.joinpath(str(idx))
    p.mkdir(exist_ok=True)
    return len(list(p.iterdir()))
'''

def write_desc(idx: int, desc: str):
    p = DESC_DIR.joinpath(str(idx))
    old_cnt = desc_cnt[idx]
    if old_cnt < 2: # lmao
        count_count[bool(old_cnt)]-=1
        count_count[bool(old_cnt)+1]+=1
    desc_cnt[idx] += 1
    heappush(pq, (desc_cnt[idx], idx))
    p.joinpath(f'{old_cnt}.txt').write_text(desc)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024*1024

def readd_if_needed(idx,old_cnt):
    if desc_cnt[idx] == old_cnt:
        heappush(pq, (old_cnt,idx))
@app.route("/")
def index():
    cnt,idx = heappop(pq)
    # this is dumb code.
    t = Timer(60*60, lambda: readd_if_needed(idx,cnt))
    t.start()
    # end of dumb code.
    return render_template('index.html', derpi_id=idx,
       progress='{:0.9f}'.format(100*(
         (count_count[1]+count_count[2]*2)/REQUIRED
    )))

@app.route('/api/submit', methods=['POST'])
def submit():
    idx,desc,ts = int(request.form['idx']), request.form['desc'],int(request.form['timestamp'])
    if time.time()-ts > 60*59:
        return 'FORM EXPIRED',500
    if not desc or len(desc) > 1000:
        return 'RESPONSE TOO SHORT / LONG', 500
    write_desc(idx, desc)
    return redirect('/', code=302)

if __name__ == '__main__':
    app.debug = True;
    app.run(debug=True, threaded=True, host='0.0.0.0', port=5000)

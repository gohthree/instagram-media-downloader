import os, re, sys, subprocess, threading, zipfile
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, jsonify, request, send_file, abort, Response

app = Flask(__name__)
BASE = Path.home() / 'Downloads' / 'IG-Downloader'
BASE.mkdir(parents=True, exist_ok=True)
MEDIA_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov'}
STATE = {'running':False, 'username':'', 'message':'准备就绪', 'error':'', 'files':[], 'logs':[]}
LOCK = threading.RLock()
PROCESS = None

def clean_user(value):
    value = value.strip()
    if not value: raise ValueError('请输入 Instagram 主页链接')
    if value.startswith('@'):
        value = value[1:]
    elif '/' in value or 'instagram.com' in value.lower():
        p = urlsplit(value if '://' in value else 'https://' + value)
        if (p.hostname or '').lower() not in ('instagram.com','www.instagram.com'):
            raise ValueError('请使用 instagram.com 主页链接')
        pieces=[x for x in p.path.split('/') if x]
        if len(pieces)!=1: raise ValueError('请输入账号主页链接，而不是帖子/Reel 链接')
        value=pieces[0]
    if not re.fullmatch(r'[A-Za-z0-9._]{1,30}',value): raise ValueError('Instagram 用户名格式不正确')
    return value

def media_for(user):
    root = BASE / user
    if not root.exists(): return []
    return sorted([p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.suffix.lower() in MEDIA_EXT],reverse=True)

def task(user, mode, limit, media_types, login_user):
    global PROCESS
    try:
        worker=Path(__file__).parent/'downloader_worker.py'
        cmd=[sys.executable,'-u',str(worker),user,'--mode',mode,'--limit',str(limit),'--types',','.join(media_types)]
        if login_user: cmd.extend(['--login-user',login_user])
        proc=subprocess.Popen(cmd,cwd=BASE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              text=True,bufsize=1,errors='replace')
        with LOCK: PROCESS=proc
        for line in proc.stdout:
            line=line.rstrip()
            with LOCK:
                STATE['logs']=(STATE['logs']+[line])[-80:]
                STATE['message']=line[:200] if line else STATE['message']
                STATE['files']=media_for(user)
        code=proc.wait()
        with LOCK:
            STATE['files']=media_for(user)
            STATE['message']='完成：共找到 %d 个媒体文件' % len(STATE['files']) if code==0 else '已停止或部分下载失败，请看日志'
            if code: STATE['error']='Instagram 可能要求登录、限流，或部分媒体无法访问。请查看下方详细日志。'
    except Exception as ex:
        with LOCK: STATE['error']=str(ex);STATE['message']='运行失败'
    finally:
        with LOCK: STATE['running']=False;PROCESS=None

@app.get('/')
def home():
    return send_file(Path(__file__).parent/'index.html')

@app.post('/api/start')
def start():
    data=request.get_json(silent=True) or {}
    try:
        user=clean_user(data.get('url',''))
        mode=data.get('mode','new')
        if mode not in ('new','all','latest'): raise ValueError('下载模式不正确')
        raw_limit = data.get('limit', 0)
        if isinstance(raw_limit, bool) or not str(raw_limit).isdigit(): raise ValueError('帖子数量必须是整数')
        limit=0 if mode == 'all' else int(raw_limit)
        if not 0 <= limit <= 10000: raise ValueError('帖子数量必须在 0 到 10000 之间')
        if mode == 'latest' and limit == 0: raise ValueError('最新 N 帖模式需要填写至少 1 帖')
        media_types=data.get('types', ['feed','carousel','reels'])
        allowed={'feed','carousel','reels','stories','highlights'}
        if not isinstance(media_types,list) or not media_types or any(x not in allowed for x in media_types): raise ValueError('请至少选择一种有效的媒体类型')
        login_user=str(data.get('login_user','')).strip()
        if login_user and not re.fullmatch(r'[A-Za-z0-9._]{1,30}',login_user): raise ValueError('登录账号用户名不正确')
        if ('stories' in media_types or 'highlights' in media_types) and not login_user: raise ValueError('Stories/Highlights 需要填写已有本机 Instaloader 会话的登录用户名')
    except (ValueError, TypeError) as ex: return jsonify(error=str(ex)),400
    with LOCK:
        if STATE['running']: return jsonify(error='已有下载任务正在运行，请先完成或停止'),409
        STATE.update(running=True,username=user,message='正在连接 Instagram…',error='',files=media_for(user),logs=[])
        threading.Thread(target=task,args=(user,mode,limit,media_types,login_user),daemon=True).start()
    return jsonify(ok=True,username=user)

@app.get('/api/status')
def status():
    with LOCK:
        if STATE['username']: STATE['files']=media_for(STATE['username'])
        return jsonify(**STATE)

@app.post('/api/stop')
def stop():
    with LOCK:
        proc=PROCESS
        if proc is not None and proc.poll() is None:
            proc.terminate()
            STATE['message']='正在停止…'
    return jsonify(ok=True)

@app.get('/media/<username>/<path:filename>')
def media(username,filename):
    if not re.fullmatch(r'[A-Za-z0-9._]{1,30}',username): abort(404)
    if Path(filename).suffix.lower() not in MEDIA_EXT: abort(404)
    root=(BASE/username).resolve()
    path=(root/filename).resolve()
    if not path.is_relative_to(root) or not path.is_file(): abort(404)
    return send_file(path)

@app.get('/api/zip/<username>')
def zip_download(username):
    if not re.fullmatch(r'[A-Za-z0-9._]{1,30}',username): abort(404)
    with LOCK:
        if STATE['running'] and STATE['username']==username: return jsonify(error='请等下载任务结束后再打包'),409
    files=media_for(username)
    if not files: abort(404)
    dest=BASE / (username+'.zip')
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for name in files: z.write(BASE/username/name,arcname=name)
    return send_file(dest,as_attachment=True,download_name=username+'.zip')

@app.post('/api/open-folder')
def open_folder():
    user=(request.get_json(silent=True) or {}).get('username','')
    if not re.fullmatch(r'[A-Za-z0-9._]{1,30}',user): return jsonify(error='无效账号'),400
    if sys.platform!='darwin': return jsonify(error='仅支持 macOS'),400
    target=BASE/user
    target.mkdir(parents=True,exist_ok=True)
    subprocess.Popen(['open',str(target)])
    return jsonify(ok=True)

if __name__=='__main__':
    import webbrowser
    threading.Timer(1.0,lambda:webbrowser.open('http://127.0.0.1:8788')).start()
    app.run(host='127.0.0.1',port=8788,debug=False,threaded=True)

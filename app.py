import os,sqlite3,json,uuid,secrets,time,calendar,logging,re,hashlib
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from functools import wraps
from urllib.parse import quote,urlencode
import requests
from flask import Flask,request,render_template,redirect,url_for,session,flash,abort,send_file
from werkzeug.security import generate_password_hash,check_password_hash
from PIL import Image,UnidentifiedImageError
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode

DATA=os.getenv('DATA_DIR','/app/data');os.makedirs(DATA,exist_ok=True);os.makedirs(DATA+'/proofs',exist_ok=True)
DB=DATA+'/app.sqlite3'; app=Flask(__name__);app.secret_key=os.getenv('SECRET_KEY','CHANGE_ME');app.config.update(MAX_CONTENT_LENGTH=5*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','1')=='1')
PLANS={'monthly':dict(name='1 Month VPN',months=1,gb=100,devices=1,price=5000),'quarterly':dict(name='3 Months VPN',months=3,gb=350,devices=2,price=15000),'halfyear':dict(name='6 Months VPN',months=6,gb=700,devices=3,price=30000)}
PAYMENTS={'KPay':os.getenv('KPAY_NUMBER','Not configured'),'Wave':os.getenv('WAVE_NUMBER','Not configured'),'AYA Pay':os.getenv('AYA_NUMBER','Not configured')}
crypto=Fernet(urlsafe_b64encode(hashlib.sha256(os.getenv('SECRET_KEY','CHANGE_ME').encode()).digest()))

MMT=ZoneInfo('Asia/Yangon')
def now():return int(time.time()*1000)
def myanmar_date(ms):
 if not ms or int(ms)<=0:return 'No expiry'
 return datetime.fromtimestamp(int(ms)/1000,MMT).strftime('%d %b %Y, %I:%M %p (Myanmar)')
def first_expiry(ms,months):
 # Billing rule: day 1 purchase -> next month day 1 at 12:00 Myanmar local time.
 # Each first purchase expires at 12:00 on the same calendar day N months later.
 local=datetime.fromtimestamp(ms/1000,MMT).replace(hour=12,minute=0,second=0,microsecond=0)
 year=local.year+(local.month-1+months)//12;month=(local.month-1+months)%12+1
 day=min(local.day,calendar.monthrange(year,month)[1])
 return int(local.replace(year=year,month=month,day=day).timestamp()*1000)
def conn():
 c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');c.execute('PRAGMA foreign_keys=ON');return c

def init():
 with conn() as c:
  c.execute('PRAGMA journal_mode=WAL')
  c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,admin INTEGER NOT NULL DEFAULT 0)')
  c.execute('CREATE TABLE IF NOT EXISTS servers (id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,url TEXT NOT NULL,token TEXT NOT NULL,inbound INTEGER NOT NULL,host TEXT NOT NULL,public_key TEXT DEFAULT "",sni TEXT DEFAULT "",short_id TEXT DEFAULT "",flow TEXT DEFAULT "xtls-rprx-vision",enabled INTEGER DEFAULT 1)')
  c.execute('CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY,server_id INTEGER NOT NULL REFERENCES servers(id),xui_id TEXT NOT NULL,xui_email TEXT NOT NULL,username TEXT NOT NULL,inbound INTEGER NOT NULL,expiry INTEGER NOT NULL DEFAULT 0,quota INTEGER NOT NULL DEFAULT 0,devices INTEGER NOT NULL DEFAULT 0,owner INTEGER REFERENCES users(id),vpn_key TEXT DEFAULT "",status TEXT DEFAULT "imported",UNIQUE(server_id,xui_id))')
  c.execute('CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),plan TEXT NOT NULL,server_id INTEGER NOT NULL REFERENCES servers(id),client_id INTEGER REFERENCES clients(id),username TEXT,method TEXT NOT NULL,proof TEXT NOT NULL,status TEXT DEFAULT "pending",created INTEGER NOT NULL,expires INTEGER,activation_error TEXT,kind TEXT NOT NULL DEFAULT "new")')
  c.execute('CREATE TABLE IF NOT EXISTS renewals (id INTEGER PRIMARY KEY,order_id INTEGER UNIQUE NOT NULL REFERENCES orders(id),client_id INTEGER NOT NULL REFERENCES clients(id),reset_at INTEGER NOT NULL,new_quota INTEGER NOT NULL,status TEXT NOT NULL DEFAULT "scheduled",error TEXT DEFAULT "")')
  c.execute('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY,order_id INTEGER,action TEXT NOT NULL,detail TEXT DEFAULT "",at INTEGER NOT NULL)')
  c.execute('CREATE TABLE IF NOT EXISTS chat_messages (id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),sender_admin INTEGER NOT NULL DEFAULT 0,body TEXT NOT NULL,created INTEGER NOT NULL)')
  c.execute('CREATE INDEX IF NOT EXISTS idx_chat_user_created ON chat_messages(user_id,id)')
  c.execute('CREATE TABLE IF NOT EXISTS speed_results (id INTEGER PRIMARY KEY, server_id INTEGER NOT NULL REFERENCES servers(id), measured INTEGER NOT NULL, download_mbps REAL, upload_mbps REAL, ping_ms REAL, error TEXT DEFAULT "")')
  c.execute('CREATE INDEX IF NOT EXISTS idx_speed_server_date ON speed_results(server_id,measured DESC)')
  if not any(x[1]=='subscription_base' for x in c.execute('PRAGMA table_info(servers)')): c.execute('ALTER TABLE servers ADD COLUMN subscription_base TEXT DEFAULT ""')
  email=os.getenv('ADMIN_EMAIL','').strip().lower();pwd=os.getenv('ADMIN_PASSWORD','')
  if email and len(pwd)>=6 and not c.execute('SELECT 1 FROM users WHERE admin=1').fetchone():c.execute('INSERT INTO users(email,password,admin) VALUES(?,?,1)',(email,generate_password_hash(pwd)))
init()
def csrf():
 if 'csrf' not in session:session['csrf']=secrets.token_urlsafe(32)
 return session['csrf']
app.jinja_env.globals['csrf_token']=csrf
app.jinja_env.filters['expiry_date']=myanmar_date
@app.before_request
def check():
 if request.path=='/telegram/webhook' or (request.path.startswith('/monitoring/report/') and request.method=='POST'):return
 if request.method=='POST' and not secrets.compare_digest(request.form.get('_csrf',''),csrf()):abort(400)
def identity():
 if not session.get('uid'):return None
 with conn() as c:return c.execute('SELECT id,email,admin FROM users WHERE id=?',(session['uid'],)).fetchone()
@app.context_processor
def common():return {'plans':PLANS,'payments':PAYMENTS,'me':identity()}
def login_needed(f):
 @wraps(f)
 def w(*a,**kw):return f(*a,**kw) if identity() else redirect(url_for('login'))
 return w
def admin_needed(f):
 @wraps(f)
 def w(*a,**kw):
  u=identity()
  if not u or not u['admin']:abort(403)
  return f(*a,**kw)
 return w

def notify(message):
 token=os.getenv('TELEGRAM_BOT_TOKEN');chat=os.getenv('TELEGRAM_CHAT_ID')
 if token and chat:
  try:requests.post('https://api.telegram.org/bot'+token+'/sendMessage',json={'chat_id':chat,'text':message},timeout=8).raise_for_status()
  except requests.RequestException:app.logger.exception('Telegram delivery failed')
def notify_order(oid,proof_path,caption,kind):
 token=os.getenv('TELEGRAM_BOT_TOKEN');chat=os.getenv('TELEGRAM_CHAT_ID')
 if not token or not chat:return
 buttons=([{'text':'✅ Approve (payment verified)','callback_data':f'ds:approve:{oid}'},{'text':'Reject','callback_data':f'ds:reject:{oid}'}] if kind=='new' else [{'text':'Existing customer: verify ownership in Admin','url':os.getenv('PUBLIC_URL','https://digitalservices.payapi.uk').rstrip('/')+'/admin'}])
 try:
  with open(proof_path,'rb') as f:
   response=requests.post(f'https://api.telegram.org/bot{token}/sendPhoto',
    data={'chat_id':chat,'caption':caption[:1024],'reply_markup':json.dumps({'inline_keyboard':[buttons]})},
    files={'photo':('payment.jpg',f,'image/jpeg')},timeout=20)
   response.raise_for_status()
 except (OSError,requests.RequestException):app.logger.exception('Telegram payment photo delivery failed')

def normalize_username(text):
 return re.sub(r'\s+','',text or '')

def subscription_link(s,sub_id):
 base=(s['subscription_base'] or '').strip()
 if not base.startswith('https://') or not sub_id:raise RuntimeError('Configure HTTPS Subscription Base URL and enable 3x-ui subscription service for this server')
 if any(ch.isspace() for ch in base):raise RuntimeError('Invalid subscription URL')
 return base.rstrip('/')+'/'+quote(sub_id,safe='')

def server(id):
 with conn() as c:return c.execute('SELECT * FROM servers WHERE id=? AND enabled=1',(id,)).fetchone()
def api(s,method,path,payload=None):
 if not s or not s['url'].startswith('https://'):raise RuntimeError('Server must have a valid HTTPS panel URL')
 r=requests.request(method,s['url'].rstrip('/')+path,headers={'Authorization':'Bearer '+crypto.decrypt(s['token'].encode()).decode()},json=payload,timeout=20)
 r.raise_for_status();obj=r.json()
 if isinstance(obj,dict) and obj.get('success') is False:raise RuntimeError('3x-ui error: '+str(obj.get('msg','unknown')))
 return obj.get('obj',obj) if isinstance(obj,dict) else obj
def extra(o):return json.loads(o) if isinstance(o,str) else (o or {})
def client_details(s,c):
 inbound=api(s,'GET',f'/panel/api/inbounds/get/{c["inbound"]}')
 settings=extra(inbound.get('settings'))
 match=next((x for x in settings.get('clients',[]) if x.get('id')==c['xui_id']),None)
 if not match:raise RuntimeError('Client not found in actual 3x-ui inbound; manual review required')
 return inbound,dict(match)
def plus_months(ms,months):
 d=datetime.fromtimestamp(ms/1000,MMT);year=d.year+(d.month-1+months)//12;month=(d.month-1+months)%12+1
 day=min(d.day,calendar.monthrange(year,month)[1]);return int(d.replace(year=year,month=month,day=day).timestamp()*1000)
def link(s,inbound,cid,label):
 if inbound.get('protocol')!='vless':raise RuntimeError('New client provisioning supports VLESS only')
 stream=extra(inbound.get('streamSettings'));net=stream.get('network','tcp');sec=stream.get('security','none')
 if net not in ('tcp','raw','ws'):raise RuntimeError('Configure a supported VLESS TCP/WS inbound')
 q={'type':net,'security':sec}
 if sec=='reality':
  rs=extra(stream.get('realitySettings'));public=s['public_key'] or rs.get('publicKey','');sni=s['sni'] or (rs.get('serverNames') or [''])[0];sid=s['short_id'] or (rs.get('shortIds') or [''])[0]
  if not public or not sni:raise RuntimeError('Set REALITY public key and SNI for selected server')
  q.update(pbk=public,sni=sni,sid=sid,fp='chrome')
 elif sec=='tls':q['sni']=s['sni'] or s['host']
 elif sec!='none':raise RuntimeError('Unsupported inbound security')
 if net=='ws':
  ws=extra(stream.get('wsSettings'));q.update(path=ws.get('path','/'),host=(ws.get('headers') or {}).get('Host',''))
 if s['flow'] and net in ('tcp','raw'):q['flow']=s['flow']
 return f'vless://{cid}@{s["host"]}:{inbound["port"]}?{urlencode(q)}#{quote(label)}'
def apply_client(s,cl,plan,expiry,do_reset):
 inbound,details=client_details(s,cl);details.update(enable=True,expiryTime=expiry,totalGB=plan['gb']*1024**3,limitIp=plan['devices'])
 api(s,'POST',f'/panel/api/clients/update/{quote(cl["xui_email"],safe="")}',details)
 if do_reset:api(s,'POST',f'/panel/api/clients/resetTraffic/{quote(cl["xui_email"],safe="")}')
 return inbound

@app.get('/')
def home():return render_template('home.html')
@app.route('/register',methods=['GET','POST'])
def register():
 if request.method=='POST':
  email=request.form.get('email','').strip().lower();p=request.form.get('password','')
  if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(p)<10:flash('Valid email and password (10+ characters) required','bad')
  else:
   try:
    with conn() as c:
     cur=c.execute('INSERT INTO users(email,password) VALUES(?,?)',(email,generate_password_hash(p)));session.clear();session['uid']=cur.lastrowid
    return redirect('/dashboard')
   except sqlite3.IntegrityError:flash('Email already registered','bad')
 return render_template('auth.html',mode='register')
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  with conn() as c:u=c.execute('SELECT * FROM users WHERE email=?',(request.form.get('email','').lower().strip(),)).fetchone()
  if u and check_password_hash(u['password'],request.form.get('password','')):
   session.clear();session['uid']=u['id'];return redirect('/admin' if u['admin'] else '/dashboard')
  time.sleep(.4);flash('Invalid credentials','bad')
 return render_template('auth.html',mode='login')
@app.post('/logout')
def logout():session.clear();return redirect('/')
@app.get('/dashboard')
@login_needed
def dashboard():
 with conn() as c:
  orders=c.execute('SELECT o.*,s.name AS server_name FROM orders o JOIN servers s ON s.id=o.server_id WHERE o.user_id=? ORDER BY o.id DESC',(identity()['id'],)).fetchall()
  owned=c.execute('SELECT cl.*,s.name AS server_name FROM clients cl JOIN servers s ON s.id=cl.server_id WHERE owner=? ORDER BY cl.id DESC',(identity()['id'],)).fetchall()
 return render_template('dashboard.html',orders=orders,owned=owned)
@app.route('/buy/<plan>',methods=['GET','POST'])
@login_needed
def buy(plan):
 if plan not in PLANS:abort(404)
 with conn() as c:servers=c.execute('SELECT id,name FROM servers WHERE enabled=1 ORDER BY id').fetchall()
 if request.method=='POST':
  kind=request.form.get('kind');sid=request.form.get('server_id',type=int);username=normalize_username(request.form.get('username',''));method=request.form.get('method');upload=request.files.get('proof')
  if not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}',username) or kind not in ('new','existing') or not server(sid) or method not in PAYMENTS or (kind=='existing' and (not username or len(username)>150)) or not upload:
   flash('Check VPN type, server, username, and payment details','bad')
  else:
   try:
    im=Image.open(upload.stream);im.verify();upload.stream.seek(0);im=Image.open(upload.stream)
    if im.format not in ('JPEG','PNG','WEBP'):raise ValueError('Unsupported image')
    filename=secrets.token_hex(24)+'.jpg';im.convert('RGB').save(DATA+'/proofs/'+filename,format='JPEG',quality=85)
    with conn() as c:oid=c.execute('INSERT INTO orders(user_id,plan,server_id,username,method,proof,created,kind) VALUES(?,?,?,?,?,?,?,?)',(identity()['id'],plan,sid,username,method,filename,now(),kind)).lastrowid
    notify_order(oid,DATA+'/proofs/'+filename,f'🧾 Order #{oid} | {kind.upper()} | Username: {username} | Plan: {plan} | Payment: {method}. Confirm actual bank receipt before approval.',kind)
    flash('Payment submitted. Admin will verify before activation.','ok');return redirect('/dashboard')
   except (UnidentifiedImageError,ValueError,OSError):flash('Upload a valid JPG, PNG, or WEBP image under 5MB','bad')
 return render_template('buy.html',plan=plan,servers=servers)
@app.get('/admin')
@admin_needed
def admin():
 with conn() as c:
  orders=c.execute('SELECT o.*,u.email,s.name AS server_name FROM orders o JOIN users u ON o.user_id=u.id JOIN servers s ON o.server_id=s.id ORDER BY o.id DESC LIMIT 300').fetchall()
  servers=c.execute('SELECT id,name,url,inbound,host,enabled FROM servers ORDER BY id').fetchall()
  counts=c.execute('SELECT server_id,COUNT(*) n FROM clients GROUP BY server_id').fetchall()
 return render_template('admin.html',orders=orders,servers=servers,counts={x['server_id']:x['n'] for x in counts})
@app.get('/admin/proof/<int:id>')
@admin_needed
def proof(id):
 with conn() as c:o=c.execute('SELECT proof FROM orders WHERE id=?',(id,)).fetchone()
 if not o or not o['proof'] or not os.path.isfile(DATA+'/proofs/'+o['proof']):abort(404)
 return send_file(DATA+'/proofs/'+o['proof'],mimetype='image/jpeg')
@app.post('/admin/servers')
@admin_needed
def add_server():
 name=request.form.get('name','').strip();url=request.form.get('url','').strip().rstrip('/');token=request.form.get('token','').strip()
 try:
  if not name or not url.startswith('https://') or not token or not request.form.get('host','').strip():raise ValueError('Name, HTTPS panel URL, token and VPN public host required')
  with conn() as c:c.execute('INSERT INTO servers(name,url,token,inbound,host,public_key,sni,short_id,flow,subscription_base) VALUES(?,?,?,?,?,?,?,?,?,?)',(name,url,crypto.encrypt(token.encode()).decode(),int(request.form['inbound']),request.form['host'].strip(),request.form.get('public_key',''),request.form.get('sni',''),request.form.get('short_id',''),request.form.get('flow','xtls-rprx-vision'),request.form.get('subscription_base','').strip()))
  flash('Server added. Verify HTTPS API connectivity before approving real orders.','ok')
 except (ValueError,sqlite3.Error) as e:flash(str(e),'bad')
 return redirect('/admin')
@app.post('/admin/servers/<int:sid>/subscription')
@admin_needed
def set_subscription(sid):
 value=request.form.get('subscription_base','').strip()
 if not re.fullmatch(r'https://[^\s?#]+',value):flash('Valid HTTPS subscription base URL required','bad');return redirect('/admin')
 with conn() as c:c.execute('UPDATE servers SET subscription_base=? WHERE id=?',(value,sid))
 flash('Subscription base URL saved. Test it against your actual 3x-ui subscription service.','ok')
 return redirect('/admin')

@app.post('/admin/import/<int:sid>')
@admin_needed
def import_clients(sid):
 if not server(sid):abort(404)
 up=request.files.get('json')
 if not up:abort(400)
 try:
  raw=up.read(3*1024*1024+1)
  if len(raw)>3*1024*1024:raise ValueError('Export too large')
  rows=json.loads(raw);count=0
  if not isinstance(rows,list):raise ValueError('Expected exported client list')
  with conn() as c:
   for obj in rows:
    cl=obj.get('client',{});inbounds=obj.get('inboundIds',[])
    if not cl.get('id') or not cl.get('email') or not inbounds:continue
    name=(cl.get('subId') or re.sub(r'\([^)]*\)$','',cl['email'])).strip()
    c.execute('INSERT INTO clients(server_id,xui_id,xui_email,username,inbound,expiry,quota,devices) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(server_id,xui_id) DO UPDATE SET xui_email=excluded.xui_email,username=excluded.username,inbound=excluded.inbound,expiry=excluded.expiry,quota=excluded.quota,devices=excluded.devices',(sid,cl['id'],cl['email'],name,int(inbounds[0]),int(cl.get('expiryTime') or 0),int(cl.get('totalGB') or 0),int(cl.get('limitIp') or 0)))
    count+=1
  flash(f'{count} client metadata rows imported (credentials excluded).','ok')
 except (ValueError,TypeError,KeyError,sqlite3.Error) as e:flash('Import failed: '+str(e),'bad')
 return redirect('/admin')
@app.post('/admin/order/<int:oid>/<action>')
@admin_needed
def decide(oid,action):
 if action not in ('approve','reject'):abort(404)
 with conn() as c:
  c.execute('BEGIN IMMEDIATE');o=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
  if not o or o['status']!='pending':flash('Order is no longer pending; manual reconciliation required for failed orders','bad');return redirect('/admin')
  if action=='reject':c.execute('UPDATE orders SET status="rejected" WHERE id=?',(oid,));return redirect('/admin')
  c.execute('UPDATE orders SET status="processing" WHERE id=?',(oid,))
 try:
  s=server(o['server_id']);plan=PLANS[o['plan']]
  if o['kind']=='existing':
   if request.form.get('ownership_verified')!='yes':raise RuntimeError('Admin must independently verify existing client ownership and acknowledge verification before approval')
   with conn() as c:
    matches=c.execute('SELECT * FROM clients WHERE server_id=? AND (username=? COLLATE NOCASE OR xui_email=? COLLATE NOCASE)',(o['server_id'],o['username'],o['username'])).fetchall()
    if len(matches)!=1:raise RuntimeError(f'Existing username matches {len(matches)} clients. Verify server/client manually; do not auto renew.')
    cl=matches[0]
    if cl['owner'] and cl['owner']!=o['user_id']:raise RuntimeError('Client already linked to another customer; verify ownership manually')
    if c.execute("SELECT 1 FROM renewals WHERE client_id=? AND status='scheduled'",(cl['id'],)).fetchone():raise RuntimeError('Renewal already scheduled on this client')
   inbound,details=client_details(s,cl)
   if details.get('email')!=cl['xui_email']:raise RuntimeError('3x-ui metadata mismatch')
   subscription=subscription_link(s,details.get('subId'))
   actual_expiry=int(details.get('expiryTime') or 0)
   start=max(now(),actual_expiry);new_expiry=plus_months(start,plan['months']) if actual_expiry>now() else first_expiry(now(),plan['months'])
   if actual_expiry>now():
    details['expiryTime']=new_expiry
    api(s,'POST',f'/panel/api/clients/update/{quote(cl["xui_email"],safe="")}',details)
    with conn() as c:
     c.execute('UPDATE clients SET owner=?,expiry=?,vpn_key=?,status="linked" WHERE id=?',(o['user_id'],new_expiry,subscription,cl['id']))
     c.execute('INSERT INTO renewals(order_id,client_id,reset_at,new_quota) VALUES(?,?,?,?)',(oid,cl['id'],actual_expiry,plan['gb']*1024**3))
     c.execute('UPDATE orders SET status="scheduled",client_id=?,expires=? WHERE id=?',(cl['id'],new_expiry,oid))
   else:
    apply_client(s,cl,plan,new_expiry,True)
    with conn() as c:
     c.execute('UPDATE clients SET owner=?,expiry=?,quota=?,devices=?,vpn_key=?,status="linked" WHERE id=?',(o['user_id'],new_expiry,plan['gb']*1024**3,plan['devices'],subscription,cl['id']))
     c.execute('UPDATE orders SET status="active",client_id=?,expires=? WHERE id=?',(cl['id'],new_expiry,oid))
  else:
   inbound=api(s,'GET',f'/panel/api/inbounds/get/{s["inbound"]}')
   cid=str(uuid.uuid4());email=f'ds_{oid}_{o["username"]}';expiry=first_expiry(now(),plan['months'])
   sub_id=secrets.token_urlsafe(18)
   key=subscription_link(s,sub_id)
   item={'id':cid,'email':email,'subId':sub_id,'enable':True,'expiryTime':expiry,'totalGB':plan['gb']*1024**3,'limitIp':plan['devices'],'flow':s['flow']}
   api(s,'POST','/panel/api/clients/add',{'client':item,'inboundIds':[s['inbound']]})
   with conn() as c:
    clid=c.execute('INSERT INTO clients(server_id,xui_id,xui_email,username,inbound,expiry,quota,devices,owner,vpn_key,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(s['id'],cid,email,email,s['inbound'],expiry,item['totalGB'],plan['devices'],o['user_id'],key,'linked')).lastrowid
    c.execute('UPDATE orders SET status="active",client_id=?,expires=? WHERE id=?',(clid,expiry,oid))
  with conn() as c:c.execute('INSERT INTO audit(order_id,action,at) VALUES(?,?,?)',(oid,'approved',now()))
  notify(f'DigitalServices order #{oid} approved ({o["kind"]})')
  flash('Approved. Check customer dashboard / scheduled queue.','ok')
 except Exception as e:
  app.logger.exception('Order %s partial or failed processing',oid)
  with conn() as c:c.execute('UPDATE orders SET status="manual_review",activation_error=? WHERE id=?',(str(e)[:250],oid))
  flash('Manual review required: no automatic retry (prevents double provisioning).','bad')
 return redirect('/admin')

@app.post('/monitoring/report/<int:sid>')
def speed_report(sid):
 expected=os.getenv('SPEED_AGENT_SECRET','')
 supplied=request.headers.get('X-DigitalServices-Agent','')
 if len(expected)<32 or not secrets.compare_digest(supplied,expected):abort(403)
 if request.content_length and request.content_length>2048:abort(413)
 obj=request.get_json(silent=True) or {}
 if not server(sid):abort(404)
 try:
  down=float(obj['download_mbps']);up=float(obj['upload_mbps']);ping=float(obj['ping_ms'])
  if not (0<=down<=100000 and 0<=up<=100000 and 0<=ping<=60000):raise ValueError()
 except (KeyError,TypeError,ValueError):abort(400)
 with conn() as c:
  c.execute('INSERT INTO speed_results(server_id,measured,download_mbps,upload_mbps,ping_ms) VALUES(?,?,?,?,?)',(sid,now(),down,up,ping))
  # Keep 100 latest records per server for bounded storage
  c.execute('DELETE FROM speed_results WHERE server_id=? AND id NOT IN (SELECT id FROM speed_results WHERE server_id=? ORDER BY measured DESC LIMIT 100)',(sid,sid))
 return {'ok':True}

def monitoring_summary(name=None):
 with conn() as c:
  rows=c.execute('SELECT id,name FROM servers WHERE enabled=1 ORDER BY name').fetchall()
  if name:rows=[r for r in rows if r['name'].casefold()==name.casefold()]
  report=[]
  for srv in rows:
   latest=c.execute('SELECT * FROM speed_results WHERE server_id=? ORDER BY measured DESC LIMIT 1',(srv['id'],)).fetchone()
   if not latest:report.append(f"{srv['name']}: No speed test data (install agent on this VPN VPS).");continue
   age=int((now()-latest['measured'])/60000)
   when=myanmar_date(latest['measured'])
   report.append(f"{srv['name']} | ↓{latest['download_mbps']:.1f} Mbps ↑{latest['upload_mbps']:.1f} Mbps | Ping {latest['ping_ms']:.1f} ms | {when} | {age} min old")
 return report

@app.post('/telegram/webhook')
def telegram_webhook():
 token=os.getenv('TELEGRAM_BOT_TOKEN','')
 secret=os.getenv('TELEGRAM_WEBHOOK_SECRET','')
 chat_id=os.getenv('TELEGRAM_CHAT_ID','')
 admin_id=os.getenv('TELEGRAM_ADMIN_USER_ID','')
 if not token or len(secret)<24 or not admin_id or not chat_id:abort(503)
 supplied=request.headers.get('X-Telegram-Bot-Api-Secret-Token','')
 if not secrets.compare_digest(supplied,secret):abort(403)
 payload=request.get_json(silent=True) or {}
 message=payload.get('message') or {}
 if message:
  sender=message.get('from') or {};chatmsg=message.get('chat') or {}
  if str(sender.get('id'))==str(admin_id) and str(chatmsg.get('id'))==str(chat_id):
   cmd=(message.get('text') or '').strip().split()
   if cmd and cmd[0].split('@')[0].lower() in ('/speedtest','/servers'):
    requested=cmd[1] if len(cmd)>1 else None
    lines=monitoring_summary(requested)
    response='📊 DigitalServices VPN speed results (measured ON each VPN server)\\n'+('\\n'.join(lines) if lines else 'Server not found')+'\\nThese are point-in-time server tests, not proof of ISP throttling.'
    notify(response)
  return {'ok':True}
 callback=payload.get('callback_query') or {}
 sender=callback.get('from') or {}
 msg=callback.get('message') or {}
 chat=msg.get('chat') or {}
 if str(sender.get('id'))!=str(admin_id) or str(chat.get('id'))!=str(chat_id):abort(403)
 data=callback.get('data','')
 match=re.fullmatch(r'ds:(confirm|approve|reject|cancel):(\d+)',data)
 if not match:return {'ok':True}
 action,oid=match.group(1),int(match.group(2))
 answer='Request received.'
 with conn() as c:row=c.execute('SELECT kind,status FROM orders WHERE id=?',(oid,)).fetchone()
 if not row or row['status']!='pending':answer='Order no longer pending. Check admin panel.'
 elif action=='cancel':answer='Cancelled. Order remains pending.'
 elif action=='confirm':answer='Use the direct Approve button on a new order. Verify bank payment first.'
 elif action=='approve' and row['kind']!='new':answer='Existing-user renewal requires independent ownership verification in the web Admin panel.'
 else:
  # Use the same internal order processing logic as Admin, with a trusted Telegram actor.
  # The before_request CSRF check is deliberately not bypassed for any normal web request.
  with app.test_request_context('/admin/order/'+str(oid)+'/'+action,method='POST',data={'_csrf':'trusted','ownership_verified':''}):
   # Unwrap only the admin decorator; the Telegram webhook already authenticated admin sender & chat.
   decide.__wrapped__(oid,action)
  with conn() as c:state=c.execute('SELECT status FROM orders WHERE id=?',(oid,)).fetchone()
  answer='Order #'+str(oid)+' now '+(state['status'] if state else 'unknown')+'.'
  try:
   requests.post(f'https://api.telegram.org/bot{token}/editMessageReplyMarkup',json={'chat_id':chat_id,'message_id':msg.get('message_id'),'reply_markup':{'inline_keyboard':[]}},timeout=8)
  except requests.RequestException:app.logger.exception('Could not clear processed Telegram order buttons')
 try:
  requests.post(f'https://api.telegram.org/bot{token}/answerCallbackQuery',json={'callback_query_id':callback.get('id'),'text':answer[:180],'show_alert':True},timeout=8)
 except requests.RequestException:app.logger.exception('Failed to answer Telegram callback')
 return {'ok':True}


@app.get('/chat/messages')
@login_needed
def chat_messages():
 user=identity()
 target=request.args.get('user_id',type=int) if user['admin'] else user['id']
 if not target:return {'messages':[]}
 with conn() as c:
  if user['admin'] and not c.execute('SELECT 1 FROM users WHERE id=? AND admin=0',(target,)).fetchone():abort(404)
  rows=c.execute('SELECT id,sender_admin,body,created FROM chat_messages WHERE user_id=? ORDER BY id DESC LIMIT 100',(target,)).fetchall()
 return {'messages':[{'id':r['id'],'sender':'Admin' if r['sender_admin'] else 'Customer','mine':bool(r['sender_admin']) if user['admin'] else not bool(r['sender_admin']),'body':r['body'],'created':datetime.fromtimestamp(r['created']/1000,MMT).strftime('%d %b %Y %I:%M %p (Myanmar)')} for r in reversed(rows)]}

@app.post('/chat/send')
@login_needed
def chat_send():
 user=identity()
 body=(request.form.get('message') or '').strip()
 if not body or len(body)>1500:abort(400)
 target=request.form.get('user_id',type=int) if user['admin'] else user['id']
 with conn() as c:
  if not target or (user['admin'] and not c.execute('SELECT 1 FROM users WHERE id=? AND admin=0',(target,)).fetchone()):abort(404)
  c.execute('INSERT INTO chat_messages(user_id,sender_admin,body,created) VALUES(?,?,?,?)',(target,int(bool(user['admin'])),body,now()))
 return {'ok':True}

@app.get('/admin/chat/inbox')
@admin_needed
def chat_inbox():
 with conn() as c:
  rows=c.execute('SELECT u.id,u.email,COUNT(m.id) AS total,MAX(m.id) AS last_id FROM users u JOIN chat_messages m ON m.user_id=u.id WHERE u.admin=0 GROUP BY u.id,u.email ORDER BY last_id DESC LIMIT 200').fetchall()
 return {'conversations':[dict(x) for x in rows]}


@app.post('/dashboard/recover/<int:cid>')
@login_needed
def recover_key(cid):
 u=identity()
 with conn() as c:cl=c.execute('SELECT * FROM clients WHERE id=? AND owner=?',(cid,u['id'])).fetchone()
 if not cl:abort(404)
 try:
  srv=server(cl['server_id'])
  inbound,details=client_details(srv,cl)
  link_value=subscription_link(srv,details.get('subId'))
  with conn() as c:c.execute('UPDATE clients SET vpn_key=? WHERE id=? AND owner=?',(link_value,cid,u['id']))
  flash('Original subscription link restored for this account.','ok')
 except Exception:
  app.logger.exception('Subscription recovery failed')
  flash('Could not restore the subscription link; contact Admin in chat.','bad')
 return redirect('/dashboard')

@app.get('/admin/maintenance')
@admin_needed
def maintenance_status():
 cutoff=now()-int(os.getenv('PAYMENT_PROOF_RETENTION_DAYS','90'))*86400000
 with conn() as c:
  count=c.execute("SELECT COUNT(*) n FROM orders WHERE created<? AND status IN ('active','rejected','scheduled') AND proof!=''",(cutoff,)).fetchone()['n']
  chats=c.execute('SELECT COUNT(*) n FROM chat_messages').fetchone()['n']
  dbbytes=os.path.getsize(DB) if os.path.exists(DB) else 0
 return {'database_mb':round(dbbytes/1048576,2),'chat_messages':chats,'payment_proofs_eligible_for_cleanup':count,'retention_days':int(os.getenv('PAYMENT_PROOF_RETENTION_DAYS','90'))}

@app.post('/admin/maintenance/prune')
@admin_needed
def maintenance_prune():
 if request.form.get('confirm')!='DELETE_OLD_PROOFS':abort(400)
 days=max(30,int(os.getenv('PAYMENT_PROOF_RETENTION_DAYS','90')))
 cutoff=now()-days*86400000
 n=0
 with conn() as c:
  rows=c.execute("SELECT id,proof FROM orders WHERE created<? AND status IN ('active','rejected','scheduled') AND proof!='' LIMIT 100",(cutoff,)).fetchall()
  for o in rows:
   path=os.path.join(DATA,'proofs',os.path.basename(o['proof']))
   try:
    if os.path.isfile(path):os.unlink(path)
   except OSError:
    app.logger.exception('Proof cleanup failed')
    continue
   c.execute("UPDATE orders SET proof='' WHERE id=?",(o['id'],))
   n+=1
 flash(f'Cleaned {n} old payment images (order history preserved).','ok')
 return redirect('/admin')

@app.get('/admin/server-health')
@admin_needed
def server_health():
 # Panel latency is a reachability diagnostic, NOT proof of ISP traffic throttling.
 results=[]
 with conn() as c:rows=c.execute('SELECT * FROM servers ORDER BY id LIMIT 50').fetchall()
 for srv in rows:
  try:
   start=time.monotonic()
   api(srv,'GET','/panel/api/inbounds/list')
   results.append({'server':srv['name'],'api':'reachable','latency_ms':round((time.monotonic()-start)*1000)})
  except (requests.RequestException,RuntimeError,ValueError) as e:
   results.append({'server':srv['name'],'api':'error','reason':type(e).__name__})
 return {'note':'Panel API reachability/latency only. This cannot determine ISP throttling; use controlled iperf3 and multi-provider comparisons.', 'servers':results}

@app.get('/health')
def health():return {'ok':True}
if __name__=='__main__':app.run(host='0.0.0.0',port=8000)

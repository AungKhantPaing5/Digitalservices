#!/usr/bin/env python3
"""Full encrypted backup/restore for DigitalServices. Run on host with services STOPPED.
Backs up .env + full data directory (database, payments, messages).
Uses scrypt + Fernet encryption; never prints password or secrets.
"""
import os,sys,tarfile,io,pathlib,getpass,secrets,hashlib
from cryptography.fernet import Fernet,InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from base64 import urlsafe_b64encode
ROOT=pathlib.Path(__file__).resolve().parent.parent
def cipher(password,salt):
 if len(password)<12:raise ValueError('Password must have at least 12 characters')
 return Fernet(urlsafe_b64encode(Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(password.encode())))
def backup(target):
 if not (ROOT/'.env').is_file() or not (ROOT/'data').is_dir():raise ValueError('Missing .env or data directory')
 buff=io.BytesIO()
 with tarfile.open(fileobj=buff,mode='w:gz') as t:
  t.add(ROOT/'.env',arcname='.env',recursive=False)
  t.add(ROOT/'data',arcname='data',recursive=True)
 salt=secrets.token_bytes(16)
 out=b'DSBAK1'+salt+cipher(getpass.getpass('Backup encryption password (12+): '),salt).encrypt(buff.getvalue())
 p=pathlib.Path(target)
 if p.exists():raise ValueError('Backup destination already exists')
 fd=os.open(str(p),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f:f.write(out)
 print('Encrypted backup saved:',p)
def restore(src):
 raw=pathlib.Path(src).read_bytes()
 if not raw.startswith(b'DSBAK1'):raise ValueError('Not a DigitalServices full backup')
 plain=cipher(getpass.getpass('Backup decryption password: '),raw[6:22]).decrypt(raw[22:])
 with tarfile.open(fileobj=io.BytesIO(plain),mode='r:gz') as t:
  members=t.getmembers()
  for m in members:
   pp=pathlib.PurePosixPath(m.name)
   if m.name not in ('.env','data') and (not pp.parts or pp.parts[0]!='data'):raise ValueError('Unrecognized backup entry')
   if pp.is_absolute() or '..' in pp.parts or not (m.isfile() or m.isdir()) or m.issym() or m.islnk():raise ValueError('Unsafe archive member')
  if not any(x.name=='.env' for x in members) or not any(x.name=='data/app.sqlite3' for x in members):raise ValueError('Incomplete backup')
  print('Validated archive. STOP web and scheduler; back up current state first.')
  if input('Type RESTORE to overwrite .env and data files: ')!='RESTORE':raise ValueError('Cancelled')
  # Require explicit operator action; reject a running Docker deployment.
  import subprocess
  result=subprocess.run(['docker','compose','ps','-q','web','scheduler'],cwd=ROOT,capture_output=True,text=True)
  if result.returncode!=0 or result.stdout.strip():raise ValueError('Stop web and scheduler before restore.')
  t.extractall(path=ROOT,filter='data')
 print('Restored. Restart services and reconcile order/client state with 3x-ui.')
if __name__=='__main__':
 try:
  if len(sys.argv)!=3 or sys.argv[1] not in ('backup','restore'):
   sys.exit('Usage: python3 scripts/full_backup.py backup /safe/path/file.enc | restore /safe/path/file.enc')
  if sys.argv[1]=='backup':backup(sys.argv[2])
  else:restore(sys.argv[2])
 except (OSError,ValueError,InvalidToken,tarfile.TarError) as e:
  sys.exit('FAILED: '+str(e))

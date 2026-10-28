#!/usr/bin/env python3
"""Run on EACH VPN server. stdlib only; speedtest-cli executable required.
Set DS_MONITOR_URL, DS_SERVER_ID, DS_SPEED_SECRET. Do not expose secret.
A speed test may use substantial network transfer. Run sparingly (e.g. every six hours).
"""
import json,os,subprocess,urllib.request,sys
base=os.environ.get('DS_MONITOR_URL','').rstrip('/')
sid=os.environ.get('DS_SERVER_ID','')
secret=os.environ.get('DS_SPEED_SECRET','')
if not base.startswith('https://') or not sid.isdecimal() or len(secret)<32:
 sys.exit('Missing DS_MONITOR_URL https URL, numeric DS_SERVER_ID, or 32+ char DS_SPEED_SECRET')
try:
 proc=subprocess.run(['speedtest-cli','--json','--secure'],capture_output=True,text=True,timeout=150,check=True)
 data=json.loads(proc.stdout)
 if data.get('error'):raise ValueError(data['error'])
 ping_ms=float(data['ping'])
 if not 0<=ping_ms<60000:
  # Some speedtest-cli endpoints incorrectly return 1800000 ms.
  # Ping a public resolver as a separate fallback measurement, not the test server.
  import re
  p=subprocess.run(['ping','-n','-c','3','-W','3','1.1.1.1'],capture_output=True,text=True,timeout=15)
  match=re.search(r'(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = [0-9.]+/([0-9.]+)/',p.stdout)
  if not match:raise ValueError('Invalid speedtest latency; independent ICMP ping failed. No data submitted.')
  ping_ms=float(match.group(1))
 payload={'download_mbps':round(float(data['download'])*8/1e6,2),'upload_mbps':round(float(data['upload'])*8/1e6,2),'ping_ms':round(ping_ms,2)}
 req=urllib.request.Request(f'{base}/monitoring/report/{sid}',json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-DigitalServices-Agent':secret},method='POST')
 with urllib.request.urlopen(req,timeout=20) as res:
  print('Reported:',res.status,'download Mbps:',payload['download_mbps'],'upload Mbps:',payload['upload_mbps'],'ping ms:',payload['ping_ms'])
except Exception as exc:
 print('Speed test/report failed:',type(exc).__name__,str(exc)[:130],file=sys.stderr);sys.exit(1)

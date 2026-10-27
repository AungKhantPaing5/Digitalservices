import time,logging
from app import app,conn,server,api,client_details,now
from urllib.parse import quote
import json
logging.basicConfig(level=logging.INFO)
while True:
 try:
  with conn() as c:jobs=c.execute('SELECT r.*,cl.server_id,cl.xui_id,cl.xui_email,cl.inbound FROM renewals r JOIN clients cl ON cl.id=r.client_id WHERE r.status="scheduled" AND r.reset_at<=? ORDER BY r.id LIMIT 20',(now(),)).fetchall()
  for job in jobs:
   with conn() as c:
    c.execute('BEGIN IMMEDIATE');res=c.execute('UPDATE renewals SET status="processing" WHERE id=? AND status="scheduled"',(job['id'],))
    if res.rowcount!=1:continue
   try:
    s=server(job['server_id']);inbound,client=client_details(s,job)
    client.update(totalGB=job['new_quota'])
    client['limitIp']={100:1,350:2,700:3}.get(int(job['new_quota']/1024**3),1)
    api(s,'POST',f'/panel/api/inbounds/updateClient/{quote(job["xui_id"])}',{'id':job['inbound'],'settings':json.dumps({'clients':[client]})})
    api(s,'POST',f'/panel/api/inbounds/{job["inbound"]}/resetClientTraffic/{quote(job["xui_email"],safe="")}')
    with conn() as c:
     c.execute('UPDATE renewals SET status="done" WHERE id=?',(job['id'],));c.execute('UPDATE clients SET quota=?,devices=? WHERE id=?',(job['new_quota'],client['limitIp'],job['client_id']))
     c.execute('UPDATE orders SET status="active" WHERE id=?',(job['order_id'],))
   except Exception as e:
    logging.exception('Scheduled renewal failed; manual review necessary')
    with conn() as c:c.execute('UPDATE renewals SET status="manual_review",error=? WHERE id=?',(str(e)[:250],job['id']))
 except Exception:logging.exception('worker loop error')
 time.sleep(60)

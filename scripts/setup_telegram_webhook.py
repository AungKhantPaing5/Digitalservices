"""Run inside the web container after setting env variables; never prints tokens."""
import os,requests,sys
token=os.getenv('TELEGRAM_BOT_TOKEN','').strip()
secret=os.getenv('TELEGRAM_WEBHOOK_SECRET','').strip()
admin=os.getenv('TELEGRAM_ADMIN_USER_ID','').strip()
chat=os.getenv('TELEGRAM_CHAT_ID','').strip()
base=os.getenv('PUBLIC_URL','https://digitalservices.payapi.uk').rstrip('/')
if not token or len(secret)<24 or not admin.isdigit() or not chat.lstrip('-').isdigit() or not base.startswith('https://'):
 sys.exit('Set TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET (24+ chars), TELEGRAM_ADMIN_USER_ID, TELEGRAM_CHAT_ID and PUBLIC_URL in .env first.')
r=requests.post(f'https://api.telegram.org/bot{token}/setWebhook',json={'url':base+'/telegram/webhook','secret_token':secret,'allowed_updates':['callback_query','message'],'drop_pending_updates':True},timeout=15)
try:result=r.json()
except ValueError:sys.exit('Telegram returned non-JSON response')
print('Webhook configured:',bool(result.get('ok')), 'URL:',base+'/telegram/webhook')
if not result.get('ok'):print('Error:',str(result.get('description','unknown'))[:160]);sys.exit(1)

import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from app import app,conn,first_expiry,MMT
class ChatTests(unittest.TestCase):
 def setUp(self):
  self.c=app.test_client()
 def test_chat_requires_login(self):
  self.assertEqual(self.c.get('/chat/messages').status_code,302)
  self.assertEqual(self.c.get('/admin/chat/inbox').status_code,302)
 def test_expiry_date_format(self):
  value=int(datetime(2026,11,27,tzinfo=timezone.utc).timestamp()*1000)
  self.assertEqual(app.jinja_env.filters['expiry_date'](value),'27 Nov 2026, 06:30 AM (Myanmar)')
 def test_month_anniversary_noon_yangon(self):
  started=datetime(2026,10,1,18,20,tzinfo=MMT)
  ms=first_expiry(int(started.timestamp()*1000),1)
  self.assertEqual(datetime.fromtimestamp(ms/1000,MMT).strftime('%Y-%m-%d %H:%M'),'2026-11-01 12:00')
if __name__=='__main__':unittest.main()

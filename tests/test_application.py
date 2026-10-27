import os,tempfile,unittest,importlib,datetime
from unittest.mock import patch
from io import BytesIO

class DigitalServicesTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory()
  os.environ['DATA_DIR']=cls.tmp.name
  os.environ['SECRET_KEY']='test-only-strong-random-secret-never-deploy'
  os.environ['COOKIE_SECURE']='0'
  os.environ['ADMIN_EMAIL']='admin@digitalservices.test'
  os.environ['ADMIN_PASSWORD']='TestingOnly!456789'
  cls.mod=importlib.import_module('app')
  cls.client=cls.mod.app.test_client()

 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()

 def token(self):
  with self.client.session_transaction() as s:
   if 'csrf' not in s:s['csrf']='unit-test-token'
   return s['csrf']

 def test_health(self):
  self.assertEqual(self.client.get('/health').json,{'ok':True})

 def test_plans(self):
  p=self.mod.PLANS
  self.assertEqual([(p[k]['gb'],p[k]['devices'],p[k]['price']) for k in ('monthly','quarterly','halfyear')],[(100,1,5000),(350,2,15000),(700,3,30000)])

 def test_month_boundary(self):
  day=datetime.datetime(2026,1,31,tzinfo=datetime.timezone.utc)
  new=datetime.datetime.fromtimestamp(self.mod.plus_months(int(day.timestamp()*1000),1)/1000,datetime.timezone.utc)
  self.assertEqual(new.date(),datetime.date(2026,2,28))

 def test_public_pages(self):
  self.assertEqual(self.client.get('/').status_code,200)
  self.assertEqual(self.client.get('/login').status_code,200)

 def test_csrf_enforced(self):
  self.assertEqual(self.client.post('/register',data={'email':'test@digitalservices.test','password':'notarealpassword'}).status_code,400)

 def test_register_login_and_admin_boundary(self):
  e='test-user@digitalservices.test';p='SafeTemporaryPass123'
  response=self.client.post('/register',data={'_csrf':self.token(),'email':e,'password':p})
  self.assertEqual(response.status_code,302)
  self.assertEqual(self.client.get('/dashboard').status_code,200)
  self.assertEqual(self.client.get('/admin').status_code,403)
  self.client.post('/logout',data={'_csrf':self.token()})
  self.assertEqual(self.client.post('/login',data={'_csrf':self.token(),'email':e,'password':p}).status_code,302)

 def test_existing_export_is_metadata_only(self):
  # This regression checks that the clients schema stores no password/auth fields.
  with self.mod.conn() as c:
   fields=[x[1] for x in c.execute('PRAGMA table_info(clients)').fetchall()]
  self.assertNotIn('password',fields)
  self.assertNotIn('auth',fields)

if __name__=='__main__':unittest.main()

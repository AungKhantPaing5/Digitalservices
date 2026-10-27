import os,tempfile,unittest,importlib
class FeatureTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.folder=tempfile.TemporaryDirectory()
  os.environ['DATA_DIR']=cls.folder.name
  os.environ['SECRET_KEY']='safe-test-only-secret-strong'
  os.environ['COOKIE_SECURE']='0'
  cls.app=importlib.import_module('app')
 @classmethod
 def tearDownClass(cls):cls.folder.cleanup()
 def test_username_removes_whitespace(self):
  self.assertEqual(self.app.normalize_username('  hello  world\t 2026  '),'helloworld2026')
 def test_subscription_link_requires_config(self):
  self.assertEqual(self.app.subscription_link({'subscription_base':'https://vpn.example.com/sub'},'abc'),'https://vpn.example.com/sub/abc')
  with self.assertRaises(RuntimeError):self.app.subscription_link({'subscription_base':''},'abc')
 def test_unauthorized_telegram_webhook(self):
  c=self.app.app.test_client()
  result=c.post('/telegram/webhook',json={'callback_query':{'data':'ds:approve:1'}})
  self.assertIn(result.status_code,(403,503))
if __name__=='__main__':unittest.main()

import importlib.util
import unittest
from unittest.mock import patch
import subprocess
spec=importlib.util.spec_from_file_location('usage','contents/code/usage.py')
u=importlib.util.module_from_spec(spec); spec.loader.exec_module(u)
class UsageTests(unittest.TestCase):
 def test_verified_shape(self):
  data=u.normalize([{'provider':'codex','usage':{'primary':{'windowMinutes':300,'usedPercent':31,'resetsAt':'2026-10-16T02:56:31Z'},'secondary':{'windowMinutes':10080,'usedPercent':5}}}])
  self.assertEqual(data['fiveHour']['remaining'],69); self.assertEqual(data['weekly']['used'],5)
 def test_missing_and_reordered(self):
  data=u.normalize([{'provider':'codex','usage':{'primary':{'windowMinutes':10080,'usedPercent':9}}}])
  self.assertIsNone(data['fiveHour']); self.assertEqual(data['weekly']['used'],9)
 def test_invalid_percent(self):
  for value in (-1,101,float('nan'),True,'10'):
   self.assertIsNone(u.normalize([{'provider':'codex','usage':{'primary':{'windowMinutes':300,'usedPercent':value}}}])['fiveHour'])
 def test_auth(self):
  self.assertIn('Authentication',u.normalize([{'provider':'codex','error':{'message':'401 unauthorized'}}])['message'])
 def test_network(self):
  self.assertFalse(u.normalize([{'provider':'codex','error':{'message':'Network error'}}])['ok'])
 def test_bad_payload(self):
  with self.assertRaises(ValueError): u.normalize({})
 def test_timeout(self):
  with patch.object(u.shutil,'which',return_value='/bin/codexbar'), patch.object(u.subprocess,'run',side_effect=subprocess.TimeoutExpired('codexbar',40)):
   self.assertIn('timed out',u.main()['message'])
 def test_missing(self):
  with patch.object(u.shutil,'which',return_value=None), patch.object(u.Path,'is_file',return_value=False):
   self.assertIn('missing',u.main()['message'])
 def test_privacy(self):
  result=u.normalize([{'provider':'codex','usage':{'accountEmail':'private@example.test','identity':{'secret':'no'}}}])
  self.assertNotIn('private',str(result)); self.assertNotIn('secret',str(result))
unittest.main()

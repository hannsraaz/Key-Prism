import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile
import unittest
from unittest.mock import patch
from PySide6 import QtWidgets
from acerrgb.app import Window
from acerrgb.settings import Settings

class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_controls_and_dry_run_lifecycle(self):
        with patch('acerrgb.app.Settings.load',return_value=Settings()), patch('acerrgb.app.Settings.save'), \
             patch('acerrgb.app.QtWidgets.QSystemTrayIcon.isSystemTrayAvailable',return_value=False):
            window=Window()
            self.assertEqual(window.effect.count(),5)
            self.assertEqual(window.engine.fps,10)
            window.effect.setCurrentText('Breathing')
            window.apply()
            self.assertTrue(window.engine.running)
            window.stop()
            window.close()
            self.assertFalse(window.engine.running)

if __name__=='__main__':
    unittest.main()

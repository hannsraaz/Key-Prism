import math
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np
from acerrgb.color import encode, parse_color
from acerrgb.effects import Rainbow, Breathing, Typing, Static, Music
from acerrgb.hardware import Hardware
from acerrgb.engine import Engine
from acerrgb.audio import Analyzer, Loopback
from acerrgb.settings import Settings

class EffectsTests(unittest.TestCase):
    def test_rainbow_cycle_seam(self):
        effect = Rainbow(duration=5)
        a,b = effect.render(5-1e-6,0),effect.render(5+1e-6,0)
        self.assertLess(max(abs(x-y) for x,y in zip(a,b)),1e-5)
        self.assertEqual(Rainbow(saturation=0).render(2,0),(1,1,1))

    def test_breathing_endpoints_gamma(self):
        effect = Breathing((1,0.5,0),4,0.1)
        self.assertEqual(effect.render(0,0),(0.1,0.05,0))
        self.assertEqual(effect.render(2,0),(1,0.5,0))
        self.assertEqual(encode((0.5,0.5,0.5)),(55,55,55))
        self.assertEqual(encode((1,1,1),0),(0,0,0))
        self.assertEqual(encode(effect.render(4,0)),encode(effect.render(0,0)))

    def test_typing_retrigger_and_exact_idle(self):
        effect = Typing((0,0,0.1),(1,0,0),0.8,1)
        peak = effect.render(0,0,True)
        self.assertAlmostEqual(peak[0],0.8)
        self.assertLess(effect.render(0.5,0)[0],peak[0])
        for i in range(1000):
            self.assertEqual(effect.render(i/1000,0,True),peak)
        self.assertEqual(effect.render(3,0),effect.idle)

    def test_frame_independent_effects(self):
        for effect in (Rainbow(),Breathing()):
            self.assertEqual(effect.render(1.234,0.1),effect.render(1.234,1/30))

class HardwareTests(unittest.TestCase):
    def test_transactions_do_not_overlap(self):
        class Bridge:
            def __init__(self):
                self.calls=[]
            def set_dchu_data(self,*args):
                self.calls.append(('set',threading.get_ident()))
                time.sleep(0.005)
                return 0x67
            def write_app_settings(self,*args):
                self.calls.append(('settings',threading.get_ident()))
                time.sleep(0.005)
        bridge=Bridge()
        hardware=Hardware(live=True,bridge=bridge)
        workers=[threading.Thread(target=hardware.write,args=((i,0,0),)) for i in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        for i in range(0,12,3):
            self.assertEqual(len({identity for _,identity in bridge.calls[i:i+3]}),1)

    def test_verified_protocol_and_dedup(self):
        bridge = Mock()
        bridge.set_dchu_data.return_value = 0x67
        hardware = Hardware(live=True,bridge=bridge)
        hardware.write((10,20,30))
        bridge.set_dchu_data.assert_called_once_with(0x67,bytes((20,10,30,0xF0)))
        self.assertEqual(bridge.write_app_settings.call_args_list[0].args,(2,0x51,bytes((20,10,0))))
        self.assertEqual(bridge.write_app_settings.call_args_list[1].args,(2,0x20,bytes((8,))))
        hardware.write((10,20,30))
        self.assertEqual(hardware.writes,1)

    def test_dry_run_never_loads_dll(self):
        with patch('acerrgb.vendor.DCHU',side_effect=AssertionError('DLL touched')):
            hardware = Hardware()
            hardware.open()
            hardware.write((255,0,128))
            self.assertEqual(hardware.last_packet,bytes((0,255,128,0xF0)))
            hardware.close()

    def test_bad_return_does_not_write_settings(self):
        bridge = Mock()
        bridge.set_dchu_data.return_value = 0
        with self.assertRaises(RuntimeError):
            Hardware(live=True,bridge=bridge).write((1,2,3))
        bridge.write_app_settings.assert_not_called()

class RecordingHardware(Hardware):
    def __init__(self, fail=False, delay=0):
        super().__init__()
        self.times=[]
        self.colors=[]
        self.fail,self.delay=fail,delay
    def write(self,rgb):
        self.times.append(time.monotonic())
        self.colors.append(rgb)
        time.sleep(self.delay)
        if self.fail:
            raise RuntimeError('test failure')
        super().write(rgb)

class EngineTests(unittest.TestCase):
    def test_static_settles_without_periodic_wakeups(self):
        hardware=RecordingHardware()
        engine=Engine(hardware,transition=0)
        engine.select(Static((1,0,0)))
        engine.start()
        time.sleep(0.15)
        frames=engine.frames
        time.sleep(0.2)
        self.assertEqual(engine.frames,frames)
        engine.stop()

    def test_ten_fps_and_coalesced_typing(self):
        hardware=RecordingHardware()
        engine=Engine(hardware,transition=0)
        engine.select(Typing())
        engine.start()
        for _ in range(1000):
            engine.press()
        time.sleep(0.36)
        self.assertTrue(engine.stop())
        self.assertGreaterEqual(len(hardware.times),3)
        self.assertLessEqual(len(hardware.times),5)
        self.assertTrue(all(b-a>=0.095 for a,b in zip(hardware.times,hardware.times[1:])))

    def test_failure_halts_after_three(self):
        hardware=RecordingHardware(fail=True)
        engine=Engine(hardware)
        engine.select(Static((1,0,0)))
        engine.start()
        time.sleep(0.4)
        engine.stop()
        self.assertEqual(len(hardware.times),3)
        self.assertIn('three failed',engine.error)

    def test_switch_keeps_current_output_and_worker(self):
        hardware=RecordingHardware()
        engine=Engine(hardware,transition=0.2)
        engine.select(Static((1,0,0)))
        engine.start()
        time.sleep(0.35)
        worker=engine._thread
        switch_index=len(hardware.colors)
        engine.select(Static((0,0,1)),brightness=0.2)
        time.sleep(0.12)
        self.assertIs(engine._thread,worker)
        self.assertEqual(hardware.colors[switch_index],(255,0,0))
        time.sleep(0.3)
        engine.stop()
        self.assertEqual(hardware.colors[-1],encode((0,0,1),0.2))

    def test_restores_only_known_state(self):
        hardware=Hardware()
        hardware.write((5,6,7))
        engine=Engine(hardware,transition=0)
        engine.select(Static((1,0,0)))
        engine.start()
        time.sleep(0.12)
        engine.stop()
        self.assertTrue(engine.restore_supported)
        self.assertEqual(hardware.last,(5,6,7))

    def test_slow_write_stop_does_not_spawn_second_worker(self):
        hardware=RecordingHardware(delay=0.15)
        engine=Engine(hardware)
        engine.select(Rainbow())
        engine.start()
        time.sleep(0.03)
        worker=engine._thread
        self.assertFalse(engine.stop(timeout=0.001))
        engine.start()
        self.assertIs(engine._thread,worker)
        self.assertTrue(engine.stop())

class AudioTests(unittest.TestCase):
    def tone(self,freq,amplitude=0.2):
        return np.sin(2*np.pi*freq*np.arange(2048)/48000)*amplitude

    def test_fft_bands(self):
        for freq,band in [(100,0),(1000,1),(6000,2)]:
            energy,beat=Analyzer().analyze(self.tone(freq),0)
            self.assertEqual(int(np.argmax(energy)),band)
            self.assertGreater(energy[band],0.9)

    def test_noise_dc_and_nan(self):
        for samples in (self.tone(100,0.0001),np.ones(2048),np.full(2048,np.nan)):
            self.assertEqual(Analyzer().analyze(samples,0),((0,0,0),False))

    def test_beat_refractory(self):
        analyzer=Analyzer()
        self.assertTrue(analyzer.analyze(self.tone(100),0)[1])
        analyzer.analyze(np.zeros(2048),0.01)
        self.assertFalse(analyzer.analyze(self.tone(100),0.05)[1])
        analyzer.analyze(np.zeros(2048),0.4)
        self.assertTrue(analyzer.analyze(self.tone(100),0.5)[1])

    def test_stale_audio_expires(self):
        capture=Loopback()
        capture._data=self.tone(100)
        capture._timestamp=time.monotonic()-1
        self.assertIsNone(capture.latest()[1])

    def test_music_silence_decays(self):
        capture=Mock(samplerate=48000)
        capture.latest.return_value=(1,self.tone(100))
        effect=Music(capture)
        peak=effect.render(0,0.1)
        self.assertGreater(peak[0],0)
        capture.latest.return_value=(2,None)
        for i in range(100):
            result=effect.render(i/10,0.1)
        self.assertLess(max(result),1e-8)

    def test_no_microphone_fallback(self):
        backend=Mock()
        backend.default_speaker.return_value=Mock(id='speaker',name='Output')
        mic=Mock(id='mic',isloopback=False)
        backend.all_microphones.return_value=[mic]
        capture=Loopback(backend=backend)
        capture.start()
        time.sleep(0.05)
        capture.stop()
        mic.recorder.assert_not_called()
        self.assertIsNone(capture.latest()[1])

    def test_device_change_reopens_matching_loopback(self):
        first=Mock(id='a',name='A')
        second=Mock(id='b',name='B')
        backend=Mock()
        current=[first]
        backend.default_speaker.side_effect=lambda:current[0]
        devices=[]
        for identity in ('a','b'):
            device=Mock(id=identity,isloopback=True)
            recorder=Mock()
            def record(numframes):
                time.sleep(0.005)
                return np.zeros((numframes,2))
            recorder.record.side_effect=record
            device.recorder.return_value.__enter__=Mock(return_value=recorder)
            device.recorder.return_value.__exit__=Mock(return_value=False)
            devices.append(device)
        backend.all_microphones.return_value=devices
        capture=Loopback(backend=backend)
        capture.start()
        time.sleep(0.05)
        current[0]=second
        deadline=time.monotonic()+2
        while not devices[1].recorder.called and time.monotonic()<deadline:
            time.sleep(0.02)
        self.assertTrue(capture.stop())
        self.assertTrue(devices[0].recorder.called)
        self.assertTrue(devices[1].recorder.called)

class SettingsTests(unittest.TestCase):
    def test_roundtrip_and_invalid_files(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            settings=Settings(effect='Typing',decay=1.3)
            settings.save(path)
            self.assertEqual(Settings.load(path),settings)
            for value in ('[]','null','{"gamma":NaN}','{"color":1}','{"brightness":-1}'):
                path.write_text(value)
                self.assertEqual(Settings.load(path),Settings())

if __name__=='__main__':
    unittest.main()

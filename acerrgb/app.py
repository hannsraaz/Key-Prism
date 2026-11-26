"""Focused Qt control panel; hardware execution remains on the engine worker."""
import sys
from PySide6 import QtCore, QtGui, QtWidgets
from .audio import Loopback
from .color import parse_color
from .effects import Static, Rainbow, Breathing, Typing, Music
from .engine import Engine
from .hardware import Hardware
from .settings import Settings
from .typing_input import TypingInput

class Window(QtWidgets.QMainWindow):
    def __init__(self, live=False, autostart=False):
        super().__init__()
        self.live = live
        self.settings = Settings.load()
        self.hardware = Hardware(live=live)
        self.engine = Engine(self.hardware)
        self.audio = Loopback()
        self.typing = TypingInput(self.engine.press)
        self._quitting = False
        self._active = False
        self.setWindowTitle('AcerRGB · Single-zone lighting' + ('' if live else ' · DRY RUN'))
        self.resize(480, 640)
        body = QtWidgets.QWidget()
        self.setCentralWidget(body)
        layout = QtWidgets.QVBoxLayout(body)
        title = QtWidgets.QLabel('Acer Aspire 7 A715-79G')
        title.setStyleSheet('font-size: 20px; font-weight: 600; padding: 10px 0;')
        layout.addWidget(title)
        layout.addWidget(QtWidgets.QLabel('Full-keyboard RGB · 10 updates/second'))
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        self.effect = QtWidgets.QComboBox()
        self.effect.addItems(['Static', 'Rainbow', 'Breathing', 'Music', 'Typing'])
        self.effect.setCurrentText(self.settings.effect)
        form.addRow('Effect', self.effect)
        self.controls = {}
        for name, label, low, high, step in [
            ('brightness','Brightness',0,1,0.05), ('duration','Cycle / breathing duration (s)',0.2,120,0.2),
            ('saturation','Rainbow saturation',0,1,0.05), ('minimum','Breathing minimum',0,1,0.05),
            ('gamma','Output gamma',1,3,0.1), ('sensitivity','Music sensitivity',0.1,5,0.1),
            ('intensity','Typing flash intensity',0,1,0.05), ('decay','Typing fade duration (s)',0.1,10,0.1)]:
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(low,high)
            spin.setSingleStep(step)
            spin.setValue(getattr(self.settings,name))
            self.controls[name] = spin
            form.addRow(label,spin)
        self.color_buttons = {}
        for name, label in [('color','Base / typing idle colour'),('flash_color','Typing flash colour')]:
            button = QtWidgets.QPushButton('#'+getattr(self.settings,name))
            button.clicked.connect(lambda checked=False, n=name: self.pick(n))
            self.color_buttons[name] = button
            form.addRow(label,button)
        row = QtWidgets.QHBoxLayout()
        for label, action in [('Start / Apply',self.apply),('Stop',self.stop),('Save',self.save)]:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(action)
            row.addWidget(button)
        layout.addLayout(row)
        self.startup = QtWidgets.QCheckBox('Start lighting when I sign in to Windows')
        self.startup.setChecked(self.settings.startup)
        layout.addWidget(self.startup)
        note = QtWidgets.QLabel('Typing uses key-down notifications only; no characters are read or saved.\n'
                               'Music listens to playback audio only.\n'
                               'Previous external lighting cannot be read back reliably; exit holds the last colour.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.status = QtWidgets.QLabel('Ready · '+('LIVE hardware' if live else 'Dry run — DLL is not loaded'))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.tray = None
        if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QtWidgets.QSystemTrayIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon),self)
            menu = QtWidgets.QMenu(self)
            menu.addAction('Open controls', self.reopen)
            menu.addAction('Stop animation', self.stop)
            menu.addAction('Quit', self.quit)
            self.tray.setContextMenu(menu)
            self.tray.setToolTip('AcerRGB single-zone lighting')
            self.tray.activated.connect(lambda reason: self.reopen() if reason == QtWidgets.QSystemTrayIcon.DoubleClick else None)
            self.tray.show()
        self.menuBar().addAction('Quit', self.quit)
        if autostart:
            QtCore.QTimer.singleShot(0,self.apply)

    def reopen(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def pick(self, name):
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor('#'+getattr(self.settings,name)), self)
        if color.isValid():
            setattr(self.settings,name,color.name()[1:])
            self.color_buttons[name].setText(color.name())

    def collect(self):
        self.settings.effect = self.effect.currentText()
        for name, widget in self.controls.items():
            setattr(self.settings,name,widget.value())
        self.settings.startup = self.startup.isChecked()
        return self.settings.validate()

    def apply(self):
        try:
            s = self.collect()
            self.typing.stop()
            if s.effect != 'Music':
                self.audio.stop(timeout=0)
            if s.effect == 'Static':
                effect = Static(parse_color(s.color))
            elif s.effect == 'Rainbow':
                effect = Rainbow(s.duration,s.saturation)
            elif s.effect == 'Breathing':
                effect = Breathing(parse_color(s.color),s.duration,s.minimum)
            elif s.effect == 'Typing':
                effect = Typing(parse_color(s.color),parse_color(s.flash_color),s.intensity,s.decay)
            else:
                self.audio.start()
                effect = Music(self.audio,s.sensitivity)
            self.engine.select(effect,s.brightness,s.gamma)
            self.engine.start()
            if s.effect == 'Typing':
                self.typing.start()
            self._active = True
            s.save()
        except Exception as exc:
            self.stop()
            self.status.setText(str(exc))

    def stop(self):
        # Keep one engine/session and its last output, so restarting/switching
        # crossfades correctly without competing DLL workers.
        self.typing.stop()
        self.audio.stop(timeout=0)
        from .color import BLACK
        self.engine.select(Static(BLACK))
        self._active = False
        self.status.setText('Stopped · fading to black')

    def save(self):
        try:
            from .startup import set_enabled
            s = self.collect()
            set_enabled(s.startup, self.live)
            s.save()
            self.status.setText('Settings saved')
        except Exception as exc:
            self.status.setText(f'Could not save settings: {exc}')

    def refresh(self):
        if self.engine.error:
            self.typing.stop()
            self.audio.stop(timeout=0)
            self.status.setText(self.engine.error)
        elif self.typing.error:
            self.status.setText('Typing input unavailable: '+self.typing.error)
        elif self._active:
            detail = self.audio.status if self.settings.effect == 'Music' else self.settings.effect
            self.status.setText(f'{detail} · {self.hardware.writes} writes · '
                                f'{self.hardware.skipped} duplicates skipped · '
                                f'{self.hardware.latency_ms:.2f} ms last write')

    def quit(self):
        self._quitting = True
        self.close()

    def closeEvent(self,event):
        if self.tray and not self._quitting:
            self.hide()
            event.ignore()
            return
        self.typing.stop()
        self.audio.stop(timeout=0)
        if not self.engine.stop():
            self.status.setText('Waiting for vendor DLL to return before closing…')
            event.ignore()
            QtCore.QTimer.singleShot(500,self.close)
            return
        if self.tray:
            self.tray.hide()
        event.accept()

def main(live=False,autostart=False):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont('Segoe UI',10))
    window = Window(live,autostart)
    window.show()
    return app.exec()

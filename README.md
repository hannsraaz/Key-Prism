# AcerRGB Single Zone

Fresh Windows application for the **Acer Aspire 7 A715-79G**, limited to
full-keyboard RGB. The only hardware foundation retained from the earlier
project is its verified `InsydeDCHU.dll` wrapper and three-call colour sequence.
No multi-zone/per-key commands, firmware changes, raw EC access, driver installs,
or command probing are used.

## Run

The local `.venv` has been installed. Double-click **Run Preview.bat** for a
hardware-free control panel. It does not load the vendor DLL. Music and Typing
still use their respective input sources when you explicitly start those effects.

**Run Lighting.bat** enables physical lighting through the existing installed
vendor interface. Opening the window does not start an effect; choose one and
press **Start / Apply**. This new application's physical lighting has not been
tested yet. Begin at the fixed 10 FPS default.

```powershell
# Recreate the environment if needed (64-bit Python 3.10+)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe launch.py          # preview / dry run
.\.venv\Scripts\python.exe launch.py --live   # physical lighting enabled
```

The copied vendor DLL is local only; obtain it from the installed Acer driver
package when moving to another installation. Do not redistribute it without
appropriate rights. Original imported source/tests are preserved under
`_imported_reference/`; they are excluded from this new application and tests.

## Effects and controls

- **Rainbow:** continuous HSV hue rotation, duration (inverse speed), saturation,
  and global brightness. The hue wraps continuously.
- **Breathing:** sinusoidal brightness, base colour, duration and minimum level.
  Gamma is applied once after modulation, before the 8-bit hardware output.
- **Music:** Windows WASAPI loopback of the default playback endpoint, FFT bass
  (20–250 Hz), midrange (250–2500 Hz), treble (2500–12000 Hz), adaptive peak gain,
  DC rejection, noise gate, adaptive bass-onset detection and beat refractory
  interval. Fast attack and slower decay map energy to RGB and brightness.
  Sensitivity is adjustable. Audio is transient memory only, never saved.
- **Typing:** global key-down notification triggers the flash colour, followed by
  a cubic decay to the idle/base colour. Intensity and decay are adjustable.
  Notifications are coalesced into one boolean; the hook never dereferences the
  key-event payload, decodes characters, stores a key history or sends data.

Edit controls and press **Start / Apply** to update. Switching uses a 350 ms
crossfade from the last output, including when brightness or gamma changes.
At 10 FPS, typing response is bounded by the next available frame (roughly
100 ms plus Windows scheduling and DLL latency); it cannot write faster than
the configured hardware cap. Very short flashes remain visible for a frame.

**Stop** fades to black and releases audio/keyboard capture. Static and settled
typing animations sleep until a change or key-down notification. Closing the
window hides it in the system tray when available; use **Quit** to exit.

Settings are atomically saved in
`%APPDATA%\AcerRGB-SingleZone\settings.json`. **Save** also applies the optional
Windows startup checkbox using the current user's Run registry key. Startup
is off by default and retains preview/live mode from the window where Save
was pressed. Nothing has enabled Windows startup during development.

## Hardware and shutdown behaviour

All rendering and hardware transactions run on one background worker. GUI and
input threads only change intent. Calls are serialized, identical 8-bit outputs
are skipped, and delayed frames never produce catch-up bursts. Three consecutive
write failures halt the worker and surface an error. Another live instance is
rejected using a named Windows mutex. This does not prevent Acer's own lighting
software from changing the keyboard independently.

The only write sequence is:

1. `SetDCHU_Data(0x67, [green, red, blue, 0xF0], 4)`
2. `WriteAppSettings(2, 0x51, 3, [green, red, 0])`
3. `WriteAppSettings(2, 0x20, 1, [8])`

`0xF0` controls the entire keyboard on this model. The observed `SetDCHU_Data`
success result is `0x67`; other results stop the transaction. App-settings return
values do not have verified success semantics, so the application does not
invent an HRESULT interpretation or claim readback verification.

**Restoration limitation:** the verified settings sequence omits blue and does
not provide reliable complete RGB/mode readback. External pre-launch lighting
therefore cannot be restored safely. Exit leaves the last colour in place. The
engine restores a previous colour only when it is already known from the same
Hardware instance. It never probes undocumented read commands. DLL calls cannot
be forcibly cancelled safely; shutdown waits for an in-flight call and reports
when it is still waiting.

Audio monitors the default endpoint once per second, clears failed capture data,
expires samples after 300 ms, and retries failures once per second. It never
falls back to a microphone or an unrelated playback endpoint.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\benchmark.py --seconds 3
.\.venv\Scripts\python.exe tools\smoke.py
```

The automated suite uses dry-run/fake hardware only. Tests cover protocol bytes,
DLL exclusion in preview, rate limiting, coalescing, failure cutoff, crossfades,
known-state restoration, shutdown races, gamma, cycle seams, typing retriggers,
FFT bands, beat detection, noise rejection, stale audio, endpoint changes,
microphone exclusion, settings validation, and Qt controls/lifecycle.

`benchmark-results.json` contains measured dry-run 10/15/20/30 FPS results.
These measure software scheduling only, **not safe physical DLL throughput**.
Windows timer resolution can lower achieved rates. The GUI remains at 10 FPS;
no system-wide timer-resolution change or busy spin is used. Higher physical
rates require a separate supervised hardware benchmark.

Implementation references: [Microsoft low-level keyboard hooks](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelkeyboardproc)
and [SoundCard WASAPI documentation](https://soundcard.readthedocs.io/en/latest/).

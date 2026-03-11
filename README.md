# Windows Audio Tester

A lightweight desktop application for diagnosing audio output issues on Windows 10. Test individual speaker channels, switch between output devices, and quickly identify problems like a dead left/right speaker or a misconfigured surround setup — all from a clean dark-themed GUI.

---

## Features

- **Per-channel testing** — click any speaker button to play a tone through that channel only
- **Sequential sweep** — "Test All Speakers" cycles through every channel in order with synchronized visual highlighting
- **Multiple channel configurations** — Stereo 2.0, 2.1, Surround 5.1, and Surround 7.1
- **Device switching** — enumerate all Windows output devices and test any of them on the fly
- **Frequency sweep tones** — each test plays a 200 Hz → 1 kHz sweep so you can hear it clearly at any volume
- **Volume control** — adjustable slider, defaults to 70%
- **Activity indicators** — LED-style dots on each speaker button light up when that channel is playing
- **Status bar** — live feedback showing device name, what is playing, and any errors

---

## Requirements

| Requirement | Version |
|---|---|
| Windows | 10 or later |
| Python | 3.10+ |
| sounddevice | 0.5+ |
| numpy | 1.24+ |

> **tkinter** is included with the standard Python installation from python.org and the Microsoft Store.

---

## Installation

### 1. Install Python

Download from [python.org](https://www.python.org/downloads/) or the Microsoft Store. Make sure **"Add Python to PATH"** is checked during installation.

### 2. Install dependencies

```bash
pip install sounddevice numpy
```

### 3. Clone or download this repository

```bash
git clone https://github.com/your-username/winAudioTest.git
cd winAudioTest
```

Or simply download `audio_tester.py` directly.

---

## Usage

```bash
python audio_tester.py
```

### Step-by-step workflow

1. **Select an output device** from the dropdown at the top-left. The app automatically pre-selects your Windows default device. Hit **↺ Refresh** if you plug in a new device while the app is open.

2. **Choose a channel configuration** that matches your speaker setup:
   - **Stereo (2.0)** — standard left/right speakers or headphones
   - **2.1 (Stereo + Sub)** — stereo pair with a subwoofer
   - **Surround 5.1** — front left/right, center, subwoofer, surround left/right
   - **Surround 7.1** — all of the above plus rear left/right

3. **Test individual speakers** by clicking their button in the speaker grid on the right. The button highlights red and its indicator dot turns teal while the tone plays. The test plays a 1.5-second frequency sweep (200–1000 Hz) through that channel only.

4. **Test all speakers at once** with the **▶ Test All Speakers** button. Each speaker is tested in sequence (0.6 s each), and the corresponding button highlights as audio plays through it.

5. **Adjust volume** with the slider. This scales the output amplitude before sending to the device — it is independent of your Windows master volume.

6. **Stop at any time** with the **■ Stop** button.

---

## Diagnosing Common Problems

### Only hearing sound from one speaker

1. Open the app and select **Stereo (2.0)**.
2. Click **Left** — do you hear sound? Click **Right** — do you hear sound?
3. If one is silent:
   - Check the physical cable is fully seated in the correct port.
   - Open **Windows Sound settings → Properties → Levels** and verify both channels are not muted.
   - Run the Windows built-in speaker test: right-click the volume icon → *Sound settings → Test*.
   - Try a different output device in the dropdown to rule out a driver issue.

### Surround speakers not working

1. Set Windows to output in the correct surround format: right-click the volume icon → *Sound settings → Device properties → Additional device properties → Configure*.
2. Select the matching speaker setup (e.g. 5.1 or 7.1) in Windows and click **Test** to let Windows verify the configuration.
3. Return to this app and test each channel individually to pinpoint which speaker is missing.

### No sound at all

- Confirm the correct device is selected in the dropdown (not a disabled or virtual device).
- Check that the volume slider is above 0% and that Windows system volume is not muted.
- Click **↺ Refresh** — the device list may have changed since launch.
- Check the status bar at the bottom for any playback error messages.

### Wrong speaker plays the tone

- Your audio device's channel mapping may differ from the Windows convention. This is common with some USB DACs and HDMI outputs.
- Try remapping channels in your device's driver/control panel or in Windows Spatial Sound settings.

---

## Project Structure

```
winAudioTest/
├── audio_tester.py   # entire application — single file, no build step needed
└── README.md
```

### Key internals

| Component | Description |
|---|---|
| `CHANNEL_CONFIGS` | Dictionary defining all speaker layouts and their channel indices |
| `generate_sweep()` | Generates a linear frequency sweep on a single channel of a multi-channel audio array |
| `generate_all_channels()` | Concatenates short tones on each channel sequentially for the "Test All" sweep |
| `SpeakerButton` | Custom `tk.Frame` subclass — button + LED indicator with hover/active states |
| `AudioTesterApp` | Main `tk.Tk` window; manages device enumeration, playback threading, and UI state |

Audio is generated with **numpy** as float32 PCM and played via **sounddevice** on a background daemon thread so the UI remains responsive. A 50 ms fade-in/fade-out window prevents audible clicks.

---

## Customisation

All visual constants are in the `COLORS` dict at the top of `audio_tester.py`. Playback behaviour can be tuned with:

```python
SAMPLE_RATE = 44100      # Hz
TEST_DURATION = 1.5      # seconds per individual channel sweep
SWEEP_FREQS = (200, 1000) # Hz start/end for the frequency sweep
```

To add a new channel configuration (e.g. a custom 4.0 quad setup), append an entry to `CHANNEL_CONFIGS` following the existing pattern — the UI will pick it up automatically.

---

## License

MIT — free to use, modify, and distribute.

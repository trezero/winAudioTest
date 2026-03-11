"""
Windows Audio Test Tool — Professional Diagnostic Suite
A GUI application to test audio output across devices and speaker channels.
"""

import tkinter as tk
from tkinter import ttk
import threading
import numpy as np
import sounddevice as sd
import math
import random

# ── Optional Windows Core Audio (pycaw) ───────────────────────────────────────
try:
    from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
    from comtypes import CLSCTX_ALL
    from ctypes import cast, POINTER
    HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False

# ── Channel definitions ────────────────────────────────────────────────────────
CHANNEL_CONFIGS = {
    "Stereo (2.0)": {
        "channels": 2,
        "speakers": [
            {"name": "Left",  "ch": 0, "icon": "◀ L"},
            {"name": "Right", "ch": 1, "icon": "R ▶"},
        ],
    },
    "2.1 (Stereo + Sub)": {
        "channels": 3,
        "speakers": [
            {"name": "Left",       "ch": 0, "icon": "◀ L"},
            {"name": "Right",      "ch": 1, "icon": "R ▶"},
            {"name": "Subwoofer",  "ch": 2, "icon": "⬤ SW"},
        ],
    },
    "Surround 5.1": {
        "channels": 6,
        "speakers": [
            {"name": "Front Left",    "ch": 0, "icon": "◀ FL"},
            {"name": "Front Right",   "ch": 1, "icon": "FR ▶"},
            {"name": "Center",        "ch": 2, "icon": "▲ C"},
            {"name": "Subwoofer",     "ch": 3, "icon": "⬤ SW"},
            {"name": "Surround Left", "ch": 4, "icon": "↙ SL"},
            {"name": "Surround Right","ch": 5, "icon": "↘ SR"},
        ],
    },
    "Surround 7.1": {
        "channels": 8,
        "speakers": [
            {"name": "Front Left",      "ch": 0, "icon": "◀ FL"},
            {"name": "Front Right",     "ch": 1, "icon": "FR ▶"},
            {"name": "Center",          "ch": 2, "icon": "▲ C"},
            {"name": "Subwoofer",       "ch": 3, "icon": "⬤ SW"},
            {"name": "Surround Left",   "ch": 4, "icon": "↙ SL"},
            {"name": "Surround Right",  "ch": 5, "icon": "↘ SR"},
            {"name": "Rear Left",       "ch": 6, "icon": "⬅ RL"},
            {"name": "Rear Right",      "ch": 7, "icon": "RR ➡"},
        ],
    },
}

WINDOWS_CH_NAMES = {
    1: ["Mono"],
    2: ["Left", "Right"],
    4: ["Front Left", "Front Right", "Rear Left", "Rear Right"],
    6: ["Front Left", "Front Right", "Center", "Subwoofer",
        "Surround Left", "Surround Right"],
    8: ["Front Left", "Front Right", "Center", "Subwoofer",
        "Surround Left", "Surround Right", "Rear Left", "Rear Right"],
}

SAMPLE_RATE = 44100
TEST_DURATION = 1.5
SWEEP_FREQS = (200, 1000)
PEAK_POLL_MS = 80

# ── Color palette (neon-dark theme matching sampleInterface.html) ──────────────
C = {
    "bg":         "#131a2b",
    "sidebar":    "#101624",
    "panel":      "#182034",
    "border":     "#263044",
    "neon":       "#00f3ff",
    "neon_dim":   "#007a80",
    "pink":       "#ff007f",
    "text":       "#e2e8f0",
    "text_dim":   "#94a3b8",
    "text_vdim":  "#5e6e82",
    "emerald":    "#10b981",
    "warn":       "#f0c040",
    "btn":        "#283854",
    "btn_hover":  "#3f546e",
    "meter_bg":   "#101520",
    "bar_idle":   "#1f2e3a",
}

_VIRTUAL_SD_NAMES = {
    "microsoft sound mapper - output",
    "microsoft sound mapper - input",
    "primary sound driver",
    "primary sound capture driver",
}


# ── Windows audio controller ──────────────────────────────────────────────────

def _names_match(sd_name: str, win_name: str) -> bool:
    a, b = sd_name.lower(), win_name.lower()
    if a in b or b in a:
        return True
    noise = {"audio", "device", "output", "speakers", "speaker", "the", "a", "an", ""}
    aw = set(a.replace("(", " ").replace(")", " ").split()) - noise
    bw = set(b.replace("(", " ").replace(")", " ").split()) - noise
    return len(aw & bw) >= 2


class WindowsAudioController:
    def __init__(self):
        self._vol = None
        self._meter = None
        self.ch_count: int = 0
        self.ch_names: list[str] = []
        self.device_label: str = ""
        self.load_error: str = ""

    def load(self, sd_device_name: str) -> bool:
        self._vol = self._meter = None
        self.ch_count = 0
        self.ch_names = []
        self.device_label = ""
        self.load_error = ""
        if not HAS_PYCAW:
            return False
        try:
            target = None
            is_virtual = sd_device_name.lower() in _VIRTUAL_SD_NAMES
            if not is_virtual:
                for d in AudioUtilities.GetAllDevices(data_flow=0, device_state=1):
                    if d.FriendlyName and _names_match(sd_device_name, d.FriendlyName):
                        target = d
                        break
            if target is None:
                target = AudioUtilities.GetSpeakers()
            vol = target.EndpointVolume
            if vol is None:
                self.load_error = "EndpointVolume unavailable."
                return False
            self._vol = vol
            self.ch_count = self._vol.GetChannelCount()
            self.ch_names = WINDOWS_CH_NAMES.get(
                self.ch_count, [f"Ch {i+1}" for i in range(self.ch_count)])
            self.device_label = target.FriendlyName or sd_device_name
            iface = target._dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
            self._meter = cast(iface, POINTER(IAudioMeterInformation))
            return True
        except Exception as e:
            self.load_error = str(e)
            return False

    @property
    def ok(self) -> bool:
        return self._vol is not None

    def get_vol(self, ch: int) -> float:
        try:
            return float(self._vol.GetChannelVolumeLevelScalar(ch))
        except Exception:
            return 1.0

    def set_vol(self, ch: int, value: float):
        try:
            self._vol.SetChannelVolumeLevelScalar(ch, max(0.0, min(1.0, float(value))), None)
        except Exception:
            pass

    def get_peak(self) -> float:
        try:
            return float(self._meter.GetPeakValue()) if self._meter else 0.0
        except Exception:
            return 0.0

    def reset_all(self):
        for ch in range(self.ch_count):
            self.set_vol(ch, 1.0)

    def equalize(self):
        if self.ch_count < 2:
            return
        mx = max(self.get_vol(ch) for ch in range(self.ch_count))
        for ch in range(self.ch_count):
            self.set_vol(ch, mx if mx > 0 else 1.0)


# ── Audio generation ──────────────────────────────────────────────────────────

def generate_sweep(channel, total_channels, duration=TEST_DURATION, sr=SAMPLE_RATE):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    f0, f1 = SWEEP_FREQS
    phase = 2 * math.pi * (f0 * t + (f1 - f0) / (2 * duration) * t ** 2)
    tone = np.sin(phase).astype(np.float32)
    fade = int(sr * 0.05)
    w = np.ones(len(t), dtype=np.float32)
    w[:fade] = np.linspace(0, 1, fade)
    w[-fade:] = np.linspace(1, 0, fade)
    tone *= w * 0.7
    audio = np.zeros((len(t), total_channels), dtype=np.float32)
    audio[:, channel] = tone
    return audio


def generate_all_channels(total_channels, duration=0.6, sr=SAMPLE_RATE):
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    tone = (np.sin(2 * math.pi * 880.0 * t) * 0.6).astype(np.float32)
    fade = int(sr * 0.03)
    w = np.ones(n, dtype=np.float32)
    w[:fade] = np.linspace(0, 1, fade)
    w[-fade:] = np.linspace(1, 0, fade)
    tone *= w
    audio = np.zeros((n * total_channels, total_channels), dtype=np.float32)
    for ch in range(total_channels):
        audio[ch * n:(ch + 1) * n, ch] = tone
    return audio


# ── Custom widgets ────────────────────────────────────────────────────────────

class NeonRadio(tk.Frame):
    """Custom radio button with neon-blue indicator circle."""

    def __init__(self, parent, text, variable, value, command=None):
        bg = parent.cget("bg") if hasattr(parent, "cget") else C["sidebar"]
        super().__init__(parent, bg=bg)
        self._var = variable
        self._value = value
        self._cmd = command

        self._cv = tk.Canvas(self, width=16, height=16, bg=bg, highlightthickness=0)
        self._cv.pack(side="left", pady=5)
        self._ring = self._cv.create_oval(1, 1, 15, 15, outline=C["border"], width=2)
        self._dot = self._cv.create_oval(5, 5, 11, 11,
                                         fill=C["neon"], outline="", state="hidden")

        self._lbl = tk.Label(self, text=text, font=("Segoe UI", 10),
                             fg=C["text_dim"], bg=bg, cursor="hand2")
        self._lbl.pack(side="left", padx=(10, 0))

        for w in (self, self._cv, self._lbl):
            w.bind("<Button-1>", self._click)
            w.configure(cursor="hand2")

        self._trace = self._var.trace_add("write", self._refresh)
        self._refresh()

    def _click(self, _=None):
        self._var.set(self._value)
        if self._cmd:
            self._cmd()

    def _refresh(self, *_):
        on = self._var.get() == self._value
        self._cv.itemconfigure(self._ring, outline=C["neon"] if on else C["border"])
        self._cv.itemconfigure(self._dot, state="normal" if on else "hidden")
        self._lbl.configure(fg=C["text"] if on else C["text_dim"])

    def destroy(self):
        try:
            self._var.trace_remove("write", self._trace)
        except Exception:
            pass
        super().destroy()


class VisualizerBar(tk.Canvas):
    """Animated vertical-bar frequency visualizer."""
    N = 12
    BW = 3
    GAP = 3

    def __init__(self, parent, width=200, height=32):
        super().__init__(parent, width=width, height=height,
                         bg=C["meter_bg"], highlightthickness=1,
                         highlightbackground=C["border"])
        self._h = height
        self._bars = []
        total = self.N * (self.BW + self.GAP) - self.GAP
        off = (width - total) // 2
        for i in range(self.N):
            x = off + i * (self.BW + self.GAP)
            bid = self.create_rectangle(x, height - 2, x + self.BW, height,
                                        fill=C["bar_idle"], outline="")
            self._bars.append((bid, x))

    def set_level(self, peak: float):
        for bid, x in self._bars:
            h = random.uniform(0.15, min(1.0, peak * 1.1)) if peak > 0.05 else 0.06
            bh = max(2, int(h * (self._h - 2)))
            self.coords(bid, x, self._h - bh, x + self.BW, self._h)
            if peak > 0.9:
                color = C["pink"]
            elif peak > 0.7:
                color = C["warn"]
            elif peak > 0.05:
                color = C["neon_dim"]
            else:
                color = C["bar_idle"]
            self.itemconfigure(bid, fill=color)


class SpeakerButton(tk.Frame):
    """Glass-panel speaker button with LED indicator and pulse animation."""

    def __init__(self, parent, label, code, command):
        super().__init__(parent, bg=C["panel"],
                         highlightthickness=1, highlightbackground=C["border"])
        self._command = command
        self._active = False
        self._pulse_job = None
        self._hover = False

        inner = tk.Frame(self, bg=C["panel"])
        inner.pack(fill="both", expand=True, padx=24, pady=16)

        self._led_cv = tk.Canvas(inner, width=8, height=8,
                                 bg=C["panel"], highlightthickness=0)
        self._led_cv.pack(pady=(0, 10))
        self._led = self._led_cv.create_oval(0, 0, 8, 8,
                                             fill=C["border"], outline="")

        self._code_lbl = tk.Label(inner, text=code,
                                  font=("Segoe UI", 22, "bold"),
                                  fg=C["text_dim"], bg=C["panel"])
        self._code_lbl.pack()

        self._name_lbl = tk.Label(inner, text=label.upper(),
                                  font=("Segoe UI", 7),
                                  fg=C["text_vdim"], bg=C["panel"])
        self._name_lbl.pack(pady=(4, 0))

        for w in (self, inner, self._led_cv, self._code_lbl, self._name_lbl):
            w.configure(cursor="hand2")
            w.bind("<Button-1>", self._click)
        for w in (self, inner, self._code_lbl, self._name_lbl):
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)

    def _click(self, _=None):
        self.set_active(True)
        self._command()

    def _enter(self, _=None):
        self._hover = True
        if not self._active:
            self.configure(highlightbackground=C["neon_dim"])
            self._code_lbl.configure(fg=C["neon"])

    def _leave(self, _=None):
        self._hover = False
        if not self._active:
            self.configure(highlightbackground=C["border"])
            self._code_lbl.configure(fg=C["text_dim"])

    def set_active(self, state: bool):
        self._active = state
        if state:
            self.configure(highlightbackground=C["neon"])
            self._led_cv.itemconfigure(self._led, fill=C["neon"])
            self._code_lbl.configure(fg=C["neon"])
            self._name_lbl.configure(fg=C["text"])
            self._start_pulse()
        else:
            self._stop_pulse()
            bdr = C["neon_dim"] if self._hover else C["border"]
            cfg = C["neon"] if self._hover else C["text_dim"]
            self.configure(highlightbackground=bdr)
            self._led_cv.itemconfigure(self._led, fill=C["border"])
            self._code_lbl.configure(fg=cfg)
            self._name_lbl.configure(fg=C["text_vdim"])

    def _start_pulse(self):
        self._stop_pulse()
        self._pulse_on = True
        self._do_pulse()

    def _do_pulse(self):
        if not self._active:
            return
        self.configure(highlightbackground=C["neon"] if self._pulse_on else C["neon_dim"])
        self._pulse_on = not self._pulse_on
        self._pulse_job = self.after(600, self._do_pulse)

    def _stop_pulse(self):
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None


# ── Main application ──────────────────────────────────────────────────────────

class AudioTesterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Windows Audio Tester")
        self.geometry("1100x820")
        self.minsize(960, 720)
        self.configure(bg=C["bg"])

        self._playing = False
        self._play_thread = None
        self._speaker_btns: list[SpeakerButton] = []
        self._win_ctrl = WindowsAudioController()

        self._ch_vol_vars: list[tk.DoubleVar] = []
        self._ch_pct_labels: list[tk.Label] = []
        self._ch_viz: list[VisualizerBar] = []
        self._active_test_ch: int | None = None
        self._peak_job = None

        self._build_ui()
        self._refresh_devices()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI skeleton ───────────────────────────────────────────────────────────

    def _build_ui(self):
        # Footer (pack first so it anchors to bottom)
        self._build_footer()
        # Header
        self._build_header()
        # Main area
        main = tk.Frame(self, bg=C["bg"])
        main.pack(fill="both", expand=True)
        # Sidebar
        self._build_sidebar(main)
        # Separator
        tk.Frame(main, bg=C["border"], width=1).pack(side="left", fill="y")
        # Center
        center = tk.Frame(main, bg=C["bg"])
        center.pack(side="left", fill="both", expand=True)
        self._build_speaker_area(center)
        tk.Frame(center, bg=C["border"], height=1).pack(fill="x")
        self._build_levels_panel(center)

    def _build_header(self):
        hdr = tk.Frame(self, bg=C["bg"], height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Icon box (simulated gradient: neon blue background)
        icon_box = tk.Frame(hdr, bg=C["neon"], padx=6, pady=6)
        icon_box.pack(side="left", padx=(24, 0), pady=10)
        tk.Label(icon_box, text="\U0001f50a", font=("Segoe UI", 11),
                 bg=C["neon"], fg="white").pack()

        title_box = tk.Frame(hdr, bg=C["bg"])
        title_box.pack(side="left", padx=(12, 0))
        tk.Label(title_box, text="Windows Audio Tester",
                 font=("Segoe UI", 15, "bold"),
                 fg=C["neon"], bg=C["bg"]).pack(anchor="w")
        tk.Label(title_box, text="PROFESSIONAL DIAGNOSTIC SUITE",
                 font=("Segoe UI", 7),
                 fg=C["text_vdim"], bg=C["bg"]).pack(anchor="w")

        tk.Label(hdr, text="Diagnose & fix speaker channel issues",
                 font=("Segoe UI", 9, "italic"),
                 fg=C["text_dim"], bg=C["bg"]).pack(side="right", padx=24)

        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")

    def _build_footer(self):
        border = tk.Frame(self, bg=C["border"], height=1)
        border.pack(fill="x", side="bottom")
        foot = tk.Frame(self, bg=C["bg"], height=28)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)

        left = tk.Frame(foot, bg=C["bg"])
        left.pack(side="left", padx=16, fill="y")
        self._status_dot_cv = tk.Canvas(left, width=8, height=8,
                                        bg=C["bg"], highlightthickness=0)
        self._status_dot_cv.pack(side="left", pady=10)
        self._status_dot = self._status_dot_cv.create_oval(
            0, 0, 8, 8, fill=C["emerald"], outline="")

        self._status_var = tk.StringVar(value="READY.")
        tk.Label(left, textvariable=self._status_var,
                 font=("Segoe UI", 7, "bold"),
                 fg=C["text_vdim"], bg=C["bg"]).pack(side="left", padx=(8, 0))

        tk.Label(foot, text="WINDOWS AUDIO TESTER",
                 font=("Segoe UI", 7),
                 fg=C["text_vdim"], bg=C["bg"]).pack(side="right", padx=16)

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=C["sidebar"], width=300)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        pad = tk.Frame(sb, bg=C["sidebar"])
        pad.pack(fill="both", expand=True, padx=24, pady=24)

        self._build_device_panel(pad)
        self._build_config_panel(pad)
        self._build_volume_panel(pad)

        # Spacer pushes actions + tips to the bottom
        tk.Frame(pad, bg=C["sidebar"]).pack(fill="both", expand=True)

        self._build_actions_panel(pad)
        self._build_tips_panel(pad)

    @staticmethod
    def _section_hdr(parent, text, bg=None):
        bg = bg or parent.cget("bg")
        tk.Label(parent, text=text.upper(),
                 font=("Segoe UI", 8, "bold"),
                 fg=C["text_dim"], bg=bg,
                 anchor="w").pack(fill="x", pady=(0, 12))

    def _build_device_panel(self, parent):
        self._section_hdr(parent, "Output Device")
        self._device_var = tk.StringVar()
        self._device_combo = ttk.Combobox(parent, textvariable=self._device_var,
                                           state="readonly", width=28,
                                           font=("Segoe UI", 9))
        self._device_combo.pack(fill="x")
        self._device_combo.bind("<<ComboboxSelected>>", self._on_device_change)

        tk.Button(parent, text="↺   Refresh Devices",
                  font=("Segoe UI", 8), fg=C["text_dim"],
                  bg=C["sidebar"], activeforeground=C["text"],
                  activebackground=C["btn_hover"],
                  relief="flat", bd=0, highlightthickness=1,
                  highlightbackground=C["border"],
                  padx=0, pady=6, cursor="hand2",
                  command=self._refresh_devices).pack(fill="x", pady=(8, 20))

    def _build_config_panel(self, parent):
        self._section_hdr(parent, "Channel Configuration")
        self._config_var = tk.StringVar(value="Stereo (2.0)")
        for name in CHANNEL_CONFIGS:
            NeonRadio(parent, text=name, variable=self._config_var,
                      value=name, command=self._rebuild_speaker_grid).pack(anchor="w")

    def _build_volume_panel(self, parent):
        row = tk.Frame(parent, bg=C["sidebar"])
        row.pack(fill="x", pady=(20, 0))
        tk.Label(row, text="TEST VOLUME",
                 font=("Segoe UI", 8, "bold"),
                 fg=C["text_dim"], bg=C["sidebar"]).pack(side="left")
        self._vol_label = tk.Label(row, text="70%",
                                   font=("Consolas", 9, "bold"),
                                   fg=C["neon"], bg=C["sidebar"])
        self._vol_label.pack(side="right")

        self._vol_var = tk.DoubleVar(value=0.7)
        tk.Scale(parent, from_=0.0, to=1.0, resolution=0.01,
                 orient="horizontal", variable=self._vol_var,
                 bg=C["sidebar"], fg=C["neon"],
                 troughcolor=C["border"],
                 highlightthickness=0, bd=0,
                 sliderrelief="flat", width=8, sliderlength=16,
                 showvalue=False).pack(fill="x", pady=(4, 0))
        self._vol_var.trace_add("write", self._update_vol_label)

    def _build_actions_panel(self, parent):
        tk.Button(parent, text="\u25b6   TEST ALL SPEAKERS",
                  font=("Segoe UI", 9, "bold"),
                  fg="white", bg=C["pink"],
                  activeforeground="white", activebackground="#cc0066",
                  relief="flat", bd=0, padx=12, pady=12, cursor="hand2",
                  command=self._test_all).pack(fill="x", pady=(0, 8))
        tk.Button(parent, text="\u25a0   STOP",
                  font=("Segoe UI", 9, "bold"),
                  fg=C["text_dim"], bg=C["btn"],
                  activeforeground=C["text"], activebackground=C["btn_hover"],
                  relief="flat", bd=0, highlightthickness=1,
                  highlightbackground=C["border"],
                  padx=12, pady=12, cursor="hand2",
                  command=self._stop).pack(fill="x")

    def _build_tips_panel(self, parent):
        box = tk.Frame(parent, bg=C["panel"],
                       highlightthickness=1, highlightbackground=C["border"])
        box.pack(fill="x", pady=(20, 0))

        hdr = tk.Frame(box, bg=C["panel"])
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(hdr, text="\u2139", font=("Segoe UI", 10),
                 fg=C["neon"], bg=C["panel"]).pack(side="left")
        tk.Label(hdr, text="  TIPS", font=("Segoe UI", 7, "bold"),
                 fg=C["neon"], bg=C["panel"]).pack(side="left")

        tk.Label(box, text=(
            "\u2022  Click a speaker icon to test that\n"
            "   channel individually.\n"
            "\u2022  Adjust channel sliders below to\n"
            "   balance your speakers.\n"
            "\u2022  Slider changes apply directly to\n"
            "   Windows and persist."
        ), font=("Segoe UI", 7), fg=C["text_vdim"], bg=C["panel"],
                 justify="left", anchor="w").pack(fill="x", padx=12, pady=(0, 10))

    # ── Center: speaker area ──────────────────────────────────────────────────

    def _build_speaker_area(self, parent):
        area = tk.Frame(parent, bg=C["bg"])
        area.pack(fill="both", expand=True, padx=32, pady=(32, 16))

        tk.Label(area, text="Speaker Layout",
                 font=("Segoe UI", 18, "bold"),
                 fg="white", bg=C["bg"]).pack()
        self._config_label = tk.Label(area, text="",
                                       font=("Segoe UI", 9),
                                       fg=C["text_vdim"], bg=C["bg"])
        self._config_label.pack(pady=(4, 0))

        self._speaker_grid = tk.Frame(area, bg=C["bg"])
        self._speaker_grid.pack(fill="both", expand=True, pady=(24, 0))

    # ── Center: levels panel ──────────────────────────────────────────────────

    def _build_levels_panel(self, parent):
        area = tk.Frame(parent, bg=C["bg"])
        area.pack(fill="x", padx=32, pady=(16, 12))

        hdr = tk.Frame(area, bg=C["bg"])
        hdr.pack(fill="x", pady=(0, 16))
        tk.Label(hdr, text="WINDOWS CHANNEL LEVELS",
                 font=("Segoe UI", 7, "bold"),
                 fg=C["text_dim"], bg=C["bg"]).pack(side="left")
        self._levels_device_label = tk.Label(
            hdr, text="", font=("Segoe UI", 7),
            fg=C["text_vdim"], bg=C["bg"])
        self._levels_device_label.pack(side="left", padx=(8, 0))

        self._levels_body = tk.Frame(area, bg=C["bg"])
        self._levels_body.pack(fill="x")

        footer = tk.Frame(area, bg=C["bg"])
        footer.pack(fill="x", pady=(16, 0))
        for txt, cmd in [("RESET ALL TO 100%", self._reset_all_vols),
                         ("EQUALIZE CHANNELS", self._equalise_vols)]:
            tk.Button(footer, text=txt,
                      font=("Segoe UI", 7, "bold"), fg=C["text"],
                      bg=C["btn"], activebackground=C["btn_hover"],
                      relief="flat", bd=0, highlightthickness=1,
                      highlightbackground=C["border"],
                      padx=12, pady=6, cursor="hand2",
                      command=cmd).pack(side="left", padx=(0, 8))

        note = tk.Frame(footer, bg=C["bg"])
        note.pack(side="right")
        tk.Label(note, text="\u2714", font=("Segoe UI", 8),
                 fg=C["emerald"], bg=C["bg"]).pack(side="left")
        tk.Label(note, text="  CHANGES ARE SAVED TO WINDOWS AND PERSIST AFTER CLOSING THIS APP.",
                 font=("Segoe UI", 7, "bold"),
                 fg=C["emerald"], bg=C["bg"]).pack(side="left")

    def _refresh_levels_ui(self):
        for w in self._levels_body.winfo_children():
            w.destroy()
        self._ch_vol_vars.clear()
        self._ch_pct_labels.clear()
        self._ch_viz.clear()

        wc = self._win_ctrl
        if not HAS_PYCAW:
            tk.Label(self._levels_body,
                     text="Channel level controls require pycaw.  Run:  pip install pycaw",
                     font=("Segoe UI", 8), fg=C["warn"], bg=C["bg"]
                     ).pack(anchor="w", pady=4)
            return
        if not wc.ok:
            err = wc.load_error or "Unknown error."
            tk.Label(self._levels_body,
                     text=f"Could not connect to Windows audio: {err}",
                     font=("Segoe UI", 8), fg=C["warn"], bg=C["bg"],
                     justify="left").pack(anchor="w", pady=4)
            return

        self._levels_device_label.configure(
            text=f"\u00b7  {wc.device_label}  \u00b7  {wc.ch_count} ch")

        for i, name in enumerate(wc.ch_names):
            row = tk.Frame(self._levels_body, bg=C["bg"])
            row.pack(fill="x", pady=4)
            row.columnconfigure(1, weight=1)

            tk.Label(row, text=name,
                     font=("Segoe UI", 10),
                     fg=C["text_dim"], bg=C["bg"],
                     width=14, anchor="w").grid(row=0, column=0, padx=(0, 12))

            var = tk.DoubleVar(value=wc.get_vol(i))
            self._ch_vol_vars.append(var)

            tk.Scale(row, from_=0.0, to=1.0, resolution=0.01,
                     orient="horizontal", variable=var,
                     bg=C["bg"], fg=C["neon"],
                     troughcolor=C["border"],
                     highlightthickness=0, bd=0,
                     sliderrelief="flat", width=8, sliderlength=16,
                     showvalue=False,
                     command=lambda v, ch=i: self._on_ch_vol(ch, v)
                     ).grid(row=0, column=1, sticky="ew", padx=(0, 8))

            pct = tk.Label(row, text=f"{int(wc.get_vol(i)*100)}%",
                           font=("Consolas", 9, "bold"),
                           fg=C["neon"], bg=C["bg"], width=4, anchor="e")
            pct.grid(row=0, column=2, padx=(0, 16))
            self._ch_pct_labels.append(pct)

            viz = VisualizerBar(row, width=200, height=32)
            viz.grid(row=0, column=3)
            self._ch_viz.append(viz)

        self._start_peak_poll()

    # ── Channel volume callbacks ──────────────────────────────────────────────

    def _on_ch_vol(self, ch, value):
        v = float(value)
        self._win_ctrl.set_vol(ch, v)
        if ch < len(self._ch_pct_labels):
            self._ch_pct_labels[ch].configure(text=f"{int(v*100)}%")
        self._set_status(
            f"Channel '{self._win_ctrl.ch_names[ch]}' set to {int(v*100)}%  — saved to Windows.")

    def _reset_all_vols(self):
        self._win_ctrl.reset_all()
        self._sync_sliders()
        self._set_status("All channels reset to 100%.")

    def _equalise_vols(self):
        self._win_ctrl.equalize()
        self._sync_sliders()
        self._set_status("All channels equalised.")

    def _sync_sliders(self):
        for i, var in enumerate(self._ch_vol_vars):
            v = self._win_ctrl.get_vol(i)
            var.set(v)
            if i < len(self._ch_pct_labels):
                self._ch_pct_labels[i].configure(text=f"{int(v*100)}%")

    # ── Peak / visualizer polling ─────────────────────────────────────────────

    def _start_peak_poll(self):
        self._stop_peak_poll()
        self._poll_peaks()

    def _stop_peak_poll(self):
        if self._peak_job:
            self.after_cancel(self._peak_job)
            self._peak_job = None

    def _poll_peaks(self):
        if self._win_ctrl.ok and self._ch_viz:
            overall = self._win_ctrl.get_peak()
            for i, viz in enumerate(self._ch_viz):
                if self._active_test_ch is not None:
                    peak = overall if i == self._active_test_ch else 0.0
                else:
                    peak = overall
                viz.set_level(peak)
        self._peak_job = self.after(PEAK_POLL_MS, self._poll_peaks)

    # ── Speaker grid ──────────────────────────────────────────────────────────

    def _rebuild_speaker_grid(self):
        for w in self._speaker_grid.winfo_children():
            w.destroy()
        self._speaker_btns.clear()

        cfg_name = self._config_var.get()
        cfg = CHANNEL_CONFIGS[cfg_name]
        speakers = cfg["speakers"]
        n = len(speakers)
        cols = 2 if n <= 4 else 3

        self._config_label.configure(
            text=f"{n} channel{'s' if n > 1 else ''}  \u2022  {cfg_name}")

        for i, sp in enumerate(speakers):
            row, col = divmod(i, cols)
            code = ''.join(c for c in sp["icon"] if c.isalpha())
            btn = SpeakerButton(
                self._speaker_grid, label=sp["name"], code=code,
                command=lambda s=sp, c=cfg: self._test_channel(s, c))
            btn.grid(row=row, column=col, padx=16, pady=10, sticky="nsew")
            self._speaker_btns.append(btn)

        for c in range(cols):
            self._speaker_grid.columnconfigure(c, weight=1)
        rows_needed = (n + cols - 1) // cols
        for r in range(rows_needed):
            self._speaker_grid.rowconfigure(r, weight=1)

    # ── Device management ─────────────────────────────────────────────────────

    def _refresh_devices(self):
        try:
            devices = sd.query_devices()
            output_devs = [(i, d["name"]) for i, d in enumerate(devices)
                           if d["max_output_channels"] > 0]
            self._device_map = {d[1]: d[0] for d in output_devs}
            names = [d[1] for d in output_devs]
            self._device_combo["values"] = names
            if names:
                try:
                    default_idx = sd.default.device[1]
                    default_name = devices[default_idx]["name"]
                    self._device_var.set(
                        default_name if default_name in names else names[0])
                except Exception:
                    self._device_var.set(names[0])
            self._set_status(f"Found {len(names)} output device(s).")
        except Exception as e:
            self._set_status(f"Error enumerating devices: {e}")
        self._rebuild_speaker_grid()
        self._load_win_audio()

    def _load_win_audio(self):
        self._stop_peak_poll()
        name = self._device_var.get()
        ok = self._win_ctrl.load(name)
        self._refresh_levels_ui()
        if ok:
            note = ""
            if HAS_PYCAW:
                is_virtual = name.lower() in _VIRTUAL_SD_NAMES
                if is_virtual or not any(
                        _names_match(name, d.FriendlyName)
                        for d in AudioUtilities.GetAllDevices(data_flow=0, device_state=1)
                        if d.FriendlyName):
                    note = "  (showing Windows default device)"
            self._set_status(
                f"Device: {self._win_ctrl.device_label}  \u00b7  "
                f"{self._win_ctrl.ch_count} Windows channels{note}")
        else:
            self._set_status(
                f"Windows audio unavailable for '{name}': {self._win_ctrl.load_error}")

    def _on_device_change(self, _=None):
        self._load_win_audio()

    # ── Playback ──────────────────────────────────────────────────────────────

    def _get_device_id(self):
        return self._device_map.get(self._device_var.get())

    def _play(self, audio, device_id, on_done=None):
        self._playing = True
        vol = self._vol_var.get()

        def _run():
            try:
                sd.play(audio * vol, samplerate=SAMPLE_RATE,
                        device=device_id, blocking=True)
            except Exception as e:
                self.after(0, lambda: self._set_status(f"Playback error: {e}"))
            finally:
                self._playing = False
                if on_done:
                    self.after(0, on_done)

        self._play_thread = threading.Thread(target=_run, daemon=True)
        self._play_thread.start()

    def _test_channel(self, speaker, config):
        if self._playing:
            self._stop()
        device_id = self._get_device_id()
        total_ch = config["channels"]
        ch = speaker["ch"]
        self._active_test_ch = ch if ch < self._win_ctrl.ch_count else None
        audio = generate_sweep(ch, total_ch)
        self._set_status(f"Testing: {speaker['name']} (ch {ch+1}/{total_ch})")
        for btn in self._speaker_btns:
            btn.set_active(False)
        self._speaker_btns[self._get_btn_index(ch)].set_active(True)

        def _done():
            self._speaker_btns[self._get_btn_index(ch)].set_active(False)
            self._active_test_ch = None
            self._set_status("READY.")
        self._play(audio, device_id, on_done=_done)

    def _test_all(self):
        if self._playing:
            self._stop()
        cfg = CHANNEL_CONFIGS[self._config_var.get()]
        audio = generate_all_channels(cfg["channels"])
        self._set_status("Testing all speakers in sequence...")
        self._animate_all(cfg["speakers"], 0)
        self._play(audio, self._get_device_id(),
                   on_done=lambda: (self._deactivate_all(),
                                    self._clear_active_ch(),
                                    self._set_status("All speakers tested.")))

    def _animate_all(self, speakers, idx):
        if not self._playing and idx > 0:
            return
        if idx < len(speakers):
            self._deactivate_all()
            self._speaker_btns[idx].set_active(True)
            ch = speakers[idx]["ch"]
            self._active_test_ch = ch if ch < self._win_ctrl.ch_count else None
            ms = int(TEST_DURATION * 1000 * 0.6)
            self.after(ms, lambda: self._animate_all(speakers, idx + 1))

    def _deactivate_all(self):
        for btn in self._speaker_btns:
            btn.set_active(False)

    def _clear_active_ch(self):
        self._active_test_ch = None

    def _get_btn_index(self, ch):
        for i, sp in enumerate(CHANNEL_CONFIGS[self._config_var.get()]["speakers"]):
            if sp["ch"] == ch:
                return i
        return 0

    def _stop(self):
        sd.stop()
        self._playing = False
        self._active_test_ch = None
        self._deactivate_all()
        self._set_status("Stopped.")

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _update_vol_label(self, *_):
        self._vol_label.configure(text=f"{int(self._vol_var.get()*100)}%")

    def _set_status(self, msg):
        self._status_var.set(msg.upper())

    def _on_close(self):
        self._stop_peak_poll()
        self._stop()
        self.destroy()


def main():
    app = AudioTesterApp()
    style = ttk.Style(app)
    style.theme_use("clam")
    style.configure("TCombobox",
                     fieldbackground=C["panel"],
                     background=C["btn"],
                     foreground=C["text"],
                     selectbackground=C["panel"],
                     selectforeground=C["text"],
                     arrowcolor=C["text_dim"],
                     bordercolor=C["border"],
                     lightcolor=C["border"],
                     darkcolor=C["border"])
    style.map("TCombobox",
              fieldbackground=[("readonly", C["panel"])],
              foreground=[("readonly", C["text"])])
    app.mainloop()


if __name__ == "__main__":
    main()

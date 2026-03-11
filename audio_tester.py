"""
Windows Audio Test Tool
A GUI application to test audio output across devices and speaker channels.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import numpy as np
import sounddevice as sd
import math

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

SAMPLE_RATE = 44100
TEST_DURATION = 1.5   # seconds per speaker sweep
SWEEP_FREQS = (200, 1000)  # Hz, start/end for frequency sweep tone

COLORS = {
    "bg":          "#1a1a2e",
    "panel":       "#16213e",
    "accent":      "#0f3460",
    "highlight":   "#e94560",
    "text":        "#eaeaea",
    "text_dim":    "#8892a4",
    "success":     "#4caf50",
    "active":      "#00d4aa",
    "btn":         "#0f3460",
    "btn_hover":   "#1a4a80",
    "btn_active":  "#e94560",
    "border":      "#2a3a5a",
}


def generate_sweep(channel: int, total_channels: int, duration: float = TEST_DURATION,
                   sr: int = SAMPLE_RATE) -> np.ndarray:
    """Generate a frequency sweep tone on a single channel."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    f_start, f_end = SWEEP_FREQS
    # Linear frequency sweep
    phase = 2 * math.pi * (f_start * t + (f_end - f_start) / (2 * duration) * t ** 2)
    tone = np.sin(phase).astype(np.float32)
    # Fade in/out to avoid clicks
    fade = int(sr * 0.05)
    window = np.ones(len(t), dtype=np.float32)
    window[:fade] = np.linspace(0, 1, fade)
    window[-fade:] = np.linspace(1, 0, fade)
    tone *= window * 0.7

    audio = np.zeros((len(t), total_channels), dtype=np.float32)
    audio[:, channel] = tone
    return audio


def generate_all_channels(total_channels: int, duration: float = 0.6,
                           sr: int = SAMPLE_RATE) -> np.ndarray:
    """Play a short tone on every channel sequentially."""
    frames_per_ch = int(sr * duration)
    t = np.linspace(0, duration, frames_per_ch, endpoint=False)
    freq = 880.0
    tone = (np.sin(2 * math.pi * freq * t) * 0.6).astype(np.float32)
    fade = int(sr * 0.03)
    window = np.ones(frames_per_ch, dtype=np.float32)
    window[:fade] = np.linspace(0, 1, fade)
    window[-fade:] = np.linspace(1, 0, fade)
    tone *= window

    audio = np.zeros((frames_per_ch * total_channels, total_channels), dtype=np.float32)
    for ch in range(total_channels):
        start = ch * frames_per_ch
        audio[start:start + frames_per_ch, ch] = tone
    return audio


class SpeakerButton(tk.Frame):
    """A visual speaker button with activity indicator."""

    def __init__(self, parent, label: str, icon: str, command, **kwargs):
        super().__init__(parent, bg=COLORS["panel"], **kwargs)
        self.command = command
        self._active = False

        self.indicator = tk.Canvas(self, width=10, height=10,
                                   bg=COLORS["panel"], highlightthickness=0)
        self.indicator.pack(side="top", pady=(8, 2))
        self._dot = self.indicator.create_oval(1, 1, 9, 9, fill=COLORS["border"], outline="")

        self.btn = tk.Button(
            self, text=f"{icon}\n{label}",
            font=("Segoe UI", 9, "bold"),
            fg=COLORS["text"], bg=COLORS["btn"],
            activeforeground=COLORS["text"], activebackground=COLORS["btn_hover"],
            relief="flat", bd=0, padx=18, pady=14, cursor="hand2",
            wraplength=80,
            command=self._on_click,
        )
        self.btn.pack(fill="both", expand=True, padx=2, pady=(0, 8))
        self.btn.bind("<Enter>", self._on_enter)
        self.btn.bind("<Leave>", self._on_leave)

    def _on_click(self):
        self.set_active(True)
        self.command()

    def _on_enter(self, _=None):
        if not self._active:
            self.btn.configure(bg=COLORS["btn_hover"])

    def _on_leave(self, _=None):
        if not self._active:
            self.btn.configure(bg=COLORS["btn"])

    def set_active(self, state: bool):
        self._active = state
        if state:
            self.btn.configure(bg=COLORS["btn_active"])
            self.indicator.itemconfigure(self._dot, fill=COLORS["active"])
        else:
            self.btn.configure(bg=COLORS["btn"])
            self.indicator.itemconfigure(self._dot, fill=COLORS["border"])


class AudioTesterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Windows Audio Tester")
        self.geometry("820x600")
        self.minsize(700, 520)
        self.configure(bg=COLORS["bg"])
        self.resizable(True, True)

        self._playing = False
        self._play_thread = None
        self._speaker_btns: list[SpeakerButton] = []

        self._build_ui()
        self._refresh_devices()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=COLORS["accent"], pady=14)
        header.pack(fill="x")
        tk.Label(header, text="  🔊  Windows Audio Tester",
                 font=("Segoe UI", 16, "bold"),
                 fg=COLORS["text"], bg=COLORS["accent"]).pack(side="left", padx=20)
        tk.Label(header, text="Diagnose speaker & channel issues",
                 font=("Segoe UI", 9), fg=COLORS["text_dim"],
                 bg=COLORS["accent"]).pack(side="left")

        # ── Main body ─────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=16)

        # ── Left column: controls ─────────────────────────────────────────────
        left = tk.Frame(body, bg=COLORS["bg"])
        left.pack(side="left", fill="y", padx=(0, 16))

        self._build_device_panel(left)
        self._build_config_panel(left)
        self._build_volume_panel(left)
        self._build_actions_panel(left)

        # ── Right column: speaker grid ────────────────────────────────────────
        right = tk.Frame(body, bg=COLORS["panel"],
                         bd=0, highlightthickness=1,
                         highlightbackground=COLORS["border"])
        right.pack(side="left", fill="both", expand=True)

        self._speaker_area_label = tk.Label(
            right, text="Speaker Layout",
            font=("Segoe UI", 11, "bold"),
            fg=COLORS["text"], bg=COLORS["panel"])
        self._speaker_area_label.pack(pady=(14, 4))

        self._config_label = tk.Label(
            right, text="",
            font=("Segoe UI", 8),
            fg=COLORS["text_dim"], bg=COLORS["panel"])
        self._config_label.pack(pady=(0, 10))

        self._speaker_grid = tk.Frame(right, bg=COLORS["panel"])
        self._speaker_grid.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready — select a device and channel config.")
        status_bar = tk.Frame(self, bg=COLORS["accent"], height=28)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(status_bar, textvariable=self._status_var,
                 font=("Segoe UI", 8), fg=COLORS["text_dim"],
                 bg=COLORS["accent"], anchor="w").pack(fill="x", padx=12)

    def _section_label(self, parent, text):
        tk.Label(parent, text=text.upper(),
                 font=("Segoe UI", 7, "bold"),
                 fg=COLORS["text_dim"], bg=COLORS["bg"],
                 anchor="w").pack(fill="x", pady=(10, 2))

    def _build_device_panel(self, parent):
        self._section_label(parent, "Output Device")
        self._device_var = tk.StringVar()
        self._device_combo = ttk.Combobox(parent, textvariable=self._device_var,
                                           state="readonly", width=30,
                                           font=("Segoe UI", 9))
        self._device_combo.pack(fill="x")
        self._device_combo.bind("<<ComboboxSelected>>", self._on_device_change)

        btn_row = tk.Frame(parent, bg=COLORS["bg"])
        btn_row.pack(fill="x", pady=(4, 0))
        tk.Button(btn_row, text="↺  Refresh",
                  font=("Segoe UI", 8), fg=COLORS["text"],
                  bg=COLORS["btn"], activebackground=COLORS["btn_hover"],
                  relief="flat", bd=0, padx=8, pady=4, cursor="hand2",
                  command=self._refresh_devices).pack(side="left")

    def _build_config_panel(self, parent):
        self._section_label(parent, "Channel Configuration")
        self._config_var = tk.StringVar(value="Stereo (2.0)")
        for name in CHANNEL_CONFIGS:
            rb = tk.Radiobutton(parent, text=name,
                                variable=self._config_var, value=name,
                                font=("Segoe UI", 9),
                                fg=COLORS["text"], bg=COLORS["bg"],
                                selectcolor=COLORS["accent"],
                                activeforeground=COLORS["text"],
                                activebackground=COLORS["bg"],
                                cursor="hand2",
                                command=self._rebuild_speaker_grid)
            rb.pack(anchor="w")

    def _build_volume_panel(self, parent):
        self._section_label(parent, "Volume")
        vol_row = tk.Frame(parent, bg=COLORS["bg"])
        vol_row.pack(fill="x")
        self._vol_var = tk.DoubleVar(value=0.7)
        tk.Scale(vol_row, from_=0.0, to=1.0, resolution=0.01,
                 orient="horizontal", variable=self._vol_var,
                 bg=COLORS["bg"], fg=COLORS["text"],
                 troughcolor=COLORS["border"],
                 highlightthickness=0, bd=0,
                 sliderrelief="flat", length=160,
                 showvalue=False).pack(side="left")
        self._vol_label = tk.Label(vol_row, text="70%",
                                   font=("Segoe UI", 9),
                                   fg=COLORS["text"], bg=COLORS["bg"], width=4)
        self._vol_label.pack(side="left", padx=4)
        self._vol_var.trace_add("write", self._update_vol_label)

    def _build_actions_panel(self, parent):
        self._section_label(parent, "Actions")
        self._test_all_btn = tk.Button(
            parent, text="▶  Test All Speakers",
            font=("Segoe UI", 9, "bold"),
            fg=COLORS["text"], bg=COLORS["highlight"],
            activeforeground=COLORS["text"],
            activebackground="#c0304d",
            relief="flat", bd=0, padx=12, pady=8, cursor="hand2",
            command=self._test_all,
        )
        self._test_all_btn.pack(fill="x", pady=(2, 4))

        self._stop_btn = tk.Button(
            parent, text="■  Stop",
            font=("Segoe UI", 9),
            fg=COLORS["text"], bg=COLORS["btn"],
            activeforeground=COLORS["text"],
            activebackground=COLORS["btn_hover"],
            relief="flat", bd=0, padx=12, pady=8, cursor="hand2",
            command=self._stop,
        )
        self._stop_btn.pack(fill="x")

        # Info box
        info = tk.Frame(parent, bg=COLORS["panel"],
                        highlightthickness=1, highlightbackground=COLORS["border"])
        info.pack(fill="x", pady=(16, 0))
        tk.Label(info, text="ℹ  Tips",
                 font=("Segoe UI", 8, "bold"),
                 fg=COLORS["active"], bg=COLORS["panel"],
                 anchor="w").pack(fill="x", padx=8, pady=(6, 2))
        tips = (
            "• Click a speaker button to test\n"
            "  that channel individually.\n"
            "• Use 'Test All' to sweep through\n"
            "  every speaker in sequence.\n"
            "• If a speaker is silent, check\n"
            "  Windows Sound settings or\n"
            "  physical cable connections."
        )
        tk.Label(info, text=tips,
                 font=("Segoe UI", 8),
                 fg=COLORS["text_dim"], bg=COLORS["panel"],
                 justify="left", anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    # ── Speaker grid ───────────────────────────────────────────────────────────

    def _rebuild_speaker_grid(self):
        for w in self._speaker_grid.winfo_children():
            w.destroy()
        self._speaker_btns.clear()

        config_name = self._config_var.get()
        config = CHANNEL_CONFIGS[config_name]
        speakers = config["speakers"]
        n = len(speakers)

        # Determine grid layout
        cols = 2 if n <= 4 else 3

        self._config_label.configure(
            text=f"{n} channel{'s' if n > 1 else ''}  ·  {config_name}")

        for i, sp in enumerate(speakers):
            row, col = divmod(i, cols)
            btn = SpeakerButton(
                self._speaker_grid,
                label=sp["name"],
                icon=sp["icon"],
                command=lambda s=sp, c=config: self._test_channel(s, c),
            )
            btn.grid(row=row, column=col, padx=8, pady=6, sticky="nsew")
            self._speaker_btns.append(btn)

        for c in range(cols):
            self._speaker_grid.columnconfigure(c, weight=1)

    # ── Device management ──────────────────────────────────────────────────────

    def _refresh_devices(self):
        try:
            devices = sd.query_devices()
            output_devs = [
                (i, d["name"])
                for i, d in enumerate(devices)
                if d["max_output_channels"] > 0
            ]
            self._device_map = {d[1]: d[0] for d in output_devs}
            names = [d[1] for d in output_devs]
            self._device_combo["values"] = names
            if names:
                # Pre-select default
                try:
                    default_idx = sd.default.device[1]
                    default_name = devices[default_idx]["name"]
                    if default_name in names:
                        self._device_var.set(default_name)
                    else:
                        self._device_var.set(names[0])
                except Exception:
                    self._device_var.set(names[0])
            self._set_status(f"Found {len(names)} output device(s).")
        except Exception as e:
            self._set_status(f"Error enumerating devices: {e}")

        self._rebuild_speaker_grid()

    def _on_device_change(self, _=None):
        self._set_status(f"Device: {self._device_var.get()}")

    # ── Playback ───────────────────────────────────────────────────────────────

    def _get_device_id(self) -> int | None:
        name = self._device_var.get()
        return self._device_map.get(name)

    def _play(self, audio: np.ndarray, device_id: int | None, total_ch: int,
              on_done=None):
        """Play audio on a background thread."""
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

    def _test_channel(self, speaker: dict, config: dict):
        if self._playing:
            self._stop()

        device_id = self._get_device_id()
        total_ch = config["channels"]
        ch = speaker["ch"]
        audio = generate_sweep(ch, total_ch)

        self._set_status(f"Testing: {speaker['name']} (ch {ch + 1}/{total_ch})  ···")

        # Deactivate all, activate this one
        for btn in self._speaker_btns:
            btn.set_active(False)
        self._speaker_btns[self._get_btn_index(ch)].set_active(True)

        def _done():
            self._speaker_btns[self._get_btn_index(ch)].set_active(False)
            self._set_status("Ready.")

        self._play(audio, device_id, total_ch, on_done=_done)

    def _test_all(self):
        if self._playing:
            self._stop()

        config_name = self._config_var.get()
        config = CHANNEL_CONFIGS[config_name]
        device_id = self._get_device_id()
        total_ch = config["channels"]
        audio = generate_all_channels(total_ch)

        self._set_status(f"Testing all speakers in sequence  ···")
        self._animate_all(config["speakers"], 0, total_ch)
        self._play(audio, device_id, total_ch,
                   on_done=lambda: (self._deactivate_all(),
                                    self._set_status("All speakers tested.")))

    def _animate_all(self, speakers, idx, total_ch):
        """Animate button highlighting in sync with audio playback."""
        if not self._playing and idx > 0:
            return
        if idx < len(speakers):
            self._deactivate_all()
            self._speaker_btns[idx].set_active(True)
            ms = int(TEST_DURATION * 1000 * 0.6)  # match generate_all_channels duration
            self.after(ms, lambda: self._animate_all(speakers, idx + 1, total_ch))

    def _deactivate_all(self):
        for btn in self._speaker_btns:
            btn.set_active(False)

    def _get_btn_index(self, ch: int) -> int:
        config = CHANNEL_CONFIGS[self._config_var.get()]
        for i, sp in enumerate(config["speakers"]):
            if sp["ch"] == ch:
                return i
        return 0

    def _stop(self):
        sd.stop()
        self._playing = False
        self._deactivate_all()
        self._set_status("Stopped.")

    # ── Utilities ──────────────────────────────────────────────────────────────

    def _update_vol_label(self, *_):
        pct = int(self._vol_var.get() * 100)
        self._vol_label.configure(text=f"{pct}%")

    def _set_status(self, msg: str):
        self._status_var.set(f"  {msg}")

    def _on_close(self):
        self._stop()
        self.destroy()


def main():
    # Style ttk combobox to match dark theme
    app = AudioTesterApp()
    style = ttk.Style(app)
    style.theme_use("clam")
    style.configure("TCombobox",
                     fieldbackground=COLORS["panel"],
                     background=COLORS["btn"],
                     foreground=COLORS["text"],
                     selectbackground=COLORS["accent"],
                     selectforeground=COLORS["text"],
                     arrowcolor=COLORS["text"],
                     bordercolor=COLORS["border"],
                     lightcolor=COLORS["border"],
                     darkcolor=COLORS["border"])
    style.map("TCombobox",
              fieldbackground=[("readonly", COLORS["panel"])],
              foreground=[("readonly", COLORS["text"])])
    app.mainloop()


if __name__ == "__main__":
    main()

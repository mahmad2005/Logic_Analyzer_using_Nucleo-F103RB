import serial
import threading
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Slider, Button, RadioButtons
from collections import deque
import time

# === Serial Setup ===
ser = serial.Serial('COM4', 921600, timeout=1)
SAMPLE_COUNT = 1000
sampling_rate_hz = 83333  # Hz

# === Trigger Settings ===
trigger_enabled = True
trigger_channel = 0
trigger_edge = "rising"
capture_running = True

# === Shared Data ===
buffer_len = 10000
channels = [deque([0] * buffer_len, maxlen=buffer_len) for _ in range(4)]
lock = threading.Lock()
frequency_channel = 0
frequency_value = 0.0

# === Serial Reader Thread ===
def serial_reader():
    global capture_running, trigger_enabled, trigger_channel, trigger_edge
    prev_bit = 0

    while True:
        if not capture_running:
            time.sleep(0.01)
            continue

        try:
            byte = ser.read(1)
            if byte and byte[0] == 0xAA:
                data = ser.read(SAMPLE_COUNT)
                if len(data) != SAMPLE_COUNT:
                    continue

                triggered = not trigger_enabled

                with lock:
                    for b in data:
                        for i in range(4):
                            bit = (b >> i) & 1
                            if i == trigger_channel and not triggered:
                                if ((trigger_edge == "rising" and prev_bit == 0 and bit == 1) or
                                    (trigger_edge == "falling" and prev_bit == 1 and bit == 0)):
                                    triggered = True
                                    for ch in channels:
                                        ch.clear()
                                prev_bit = bit

                            if triggered:
                                channels[i].append(bit)
        except:
            continue

threading.Thread(target=serial_reader, daemon=True).start()

# === Plot Setup ===
fig, ax = plt.subplots(figsize=(14, 6))
lines = [ax.plot([], [], label=f'CH{i}')[0] for i in range(4)]
offsets = [1.0, 2.5, 4.0, 5.5]
ax.set_ylim(0, 7)
ax.set_xlim(0, buffer_len * 1e6 / sampling_rate_hz)
ax.set_xlabel("Time (µs)")
ax.set_ylabel("Logic Level")
ax.set_title("Real-Time 4-bit Logic Analyzer (Trigger Mode)")
ax.grid(True)
ax.legend(loc='upper right')

# === Enable Zoom/Pan Toolbar ===
fig.canvas.manager.toolbar_visible = True
fig.canvas.mpl_connect('scroll_event', lambda event: None)  # Ensures scroll-to-zoom works

# === Widgets ===
slider_ax = plt.axes([0.20, 0.02, 0.62, 0.03])
buffer_slider = Slider(slider_ax, 'Window Size', 100, 500000, valinit=buffer_len, valstep=100)

freq_label_ax = plt.axes([0.01, 0.08, 0.08, 0.15])
freq_label_ax.axis('off')
freq_text = freq_label_ax.text(0.01, 0.5, "Freq: -- Hz", fontsize=10, va='center')

button_ax = plt.axes([0.89, 0.02, 0.1, 0.04])
run_stop_button = Button(button_ax, 'Run/Stop')
def toggle_run(event):
    global capture_running
    capture_running = not capture_running
run_stop_button.on_clicked(toggle_run)

radio_ax = plt.axes([0.01, 0.4, 0.08, 0.15])
trigger_ch_radio = RadioButtons(radio_ax, ('CH0', 'CH1', 'CH2', 'CH3'))
def set_trigger_channel(label):
    global trigger_channel, frequency_channel
    ch = int(label[-1])
    trigger_channel = ch
    frequency_channel = ch
trigger_ch_radio.on_clicked(set_trigger_channel)

radio_edge_ax = plt.axes([0.01, 0.2, 0.08, 0.15])
trigger_edge_radio = RadioButtons(radio_edge_ax, ('rising', 'falling'))
def set_trigger_edge(label):
    global trigger_edge
    trigger_edge = label
trigger_edge_radio.on_clicked(set_trigger_edge)

button_trig_ax = plt.axes([0.01, 0.02, 0.1, 0.05])
trig_toggle_button = Button(button_trig_ax, 'Trig ON/OFF')
def toggle_trigger(event):
    global trigger_enabled
    trigger_enabled = not trigger_enabled
trig_toggle_button.on_clicked(toggle_trigger)

# === Plot Update ===
def update(frame):
    global buffer_len, frequency_value
    new_len = int(buffer_slider.val)

    if new_len != buffer_len:
        buffer_len = new_len
        time_per_sample = 1e6 / sampling_rate_hz
        ax.set_xlim(0, buffer_len * time_per_sample)
        ax.set_xticks([i * buffer_len * time_per_sample / 10 for i in range(11)])
        with lock:
            for i in range(4):
                channels[i] = deque(list(channels[i])[-buffer_len:], maxlen=buffer_len)

    x_vals = [i * (1e6 / sampling_rate_hz) for i in range(buffer_len)]

    with lock:
        for i in range(4):
            y = [v + offsets[i] for v in channels[i]]
            lines[i].set_data(x_vals[:len(y)], y)

        # Frequency Detection
        bits = list(channels[frequency_channel])
        edge_indices = [i for i in range(1, len(bits)) if bits[i-1] == 0 and bits[i] == 1]
        if len(edge_indices) >= 2:
            periods = [(edge_indices[i+1] - edge_indices[i]) for i in range(len(edge_indices)-1)]
            avg_period_samples = sum(periods) / len(periods)
            frequency_value = sampling_rate_hz / avg_period_samples
        else:
            frequency_value = 0.0

    freq_text.set_text(f"Rising Edge Freq (CH{frequency_channel}): {frequency_value:.2f} Hz")
    return lines

ani = animation.FuncAnimation(fig, update, interval=50, blit=True)
plt.subplots_adjust(bottom=0.25)
plt.show()

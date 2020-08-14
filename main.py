from pynput.mouse import Listener, Button
from enum import Enum
import time
import csv
import statistics
import tkinter as tk
import threading


class MouseEvent(Enum):
    MOVED = 1
    LEFT_MOUSE_PRESSED = 2
    LEFT_MOUSE_RELEASED = 3
    RIGHT_MOUSE_PRESSED = 4
    RIGHT_MOUSE_RELEASED = 5
    MIDDLE_MOUSE_PRESSED = 6
    MIDDLE_MOUSE_RELEASED = 7

    @staticmethod
    def of_button(button, pressed):
        if pressed:
            if button == Button.right:
                return MouseEvent.RIGHT_MOUSE_PRESSED
            elif button == Button.left:
                return MouseEvent.LEFT_MOUSE_PRESSED
            else:
                return MouseEvent.MIDDLE_MOUSE_PRESSED
        else:
            if button == Button.right:
                return MouseEvent.RIGHT_MOUSE_RELEASED
            elif button == Button.left:
                return MouseEvent.LEFT_MOUSE_RELEASED
            else:
                return MouseEvent.MIDDLE_MOUSE_RELEASED


class MouseRecorder:
    def __init__(self):
        self.start_time = None
        self.csv_file = None
        self.listener = None
        self.is_recording = False

    def on_move(self, x, y):
        self.write(MouseEvent.MOVED, x, y)

    def on_click(self, x, y, button, pressed):
        self.write(MouseEvent.of_button(button, pressed), x, y)

    def write(self, event, x, y):
        self.csv_file.writerow([event.name, x, y, time.perf_counter() - self.start_time])

    def start(self):
        self.start_time = time.perf_counter()
        self.is_recording = True
        with open('mouse-recording.csv', 'w', newline='', buffering=1) as csv_file:
            field_names = ['event', 'x', 'y', 'time']
            self.csv_file = csv.writer(csv_file, quoting=csv.QUOTE_NONNUMERIC)
            self.csv_file.writerow(field_names)
            with Listener(
                    on_move=self.on_move,
                    on_click=self.on_click) as listener:
                self.listener = listener
                listener.join()

    def stop(self):
        self.listener.stop()
        self.is_recording = False


class ClickAnalyzer:
    def __init__(self, csvfile_path):
        self.file_path = csvfile_path
        self.left_click_durations_ms = []

    def analyze(self):
        with open(self.file_path, newline='') as csvfile:
            csv_reader = csv.reader(csvfile)
            next(csv_reader)
            d = analyze_mouse_pressed_duration(csv_reader)
            print(d)
            csvfile.seek(0)
            next(csv_reader)
            c = analyze_time_between_clicks(csv_reader)
            print(c)


def analyze_mouse_pressed_duration(csv_reader):
    durations_ms = []
    is_pressed = False
    left_mouse_down_time = None

    for row in csv_reader:
        print(row)
        event_of_interest = MouseEvent.LEFT_MOUSE_RELEASED.name if is_pressed else MouseEvent.LEFT_MOUSE_PRESSED.name
        current_event = row[0]
        if current_event == event_of_interest:
            if current_event == MouseEvent.LEFT_MOUSE_RELEASED.name:
                durations_ms.append(float(row[3]) - left_mouse_down_time)
            else:
                left_mouse_down_time = float(row[3])
            is_pressed = current_event == MouseEvent.LEFT_MOUSE_PRESSED.name

    return statistics.NormalDist.from_samples(durations_ms)


def analyze_time_between_clicks(csv_reader):
    times = []
    previous = None
    for row in csv_reader:
        event = row[0]
        if event == MouseEvent.LEFT_MOUSE_PRESSED.name:
            tm = float(row[3])
            if previous is not None:
                times.append(tm - previous)
            previous = tm

    return statistics.NormalDist.from_samples(times)


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()
        self.mouse_recorder = MouseRecorder()

    def create_widgets(self):
        self.hi_there = tk.Button(self)
        self.hi_there["text"] = "Start recording"
        self.hi_there["command"] = self.start_recording
        self.hi_there.pack(side="top")

        self.quit = tk.Button(self, text="QUIT", fg="red",
                              command=self.master.destroy)
        self.quit.pack(side="bottom")

    def start_recording(self):
        self.recording_thread = threading.Thread(target=self.mouse_recorder.start)
        self.recording_thread.start()
        self.hi_there["text"] = "Stop recording"
        self.hi_there["command"] = self.stop_recording

    def stop_recording(self):
        self.mouse_recorder.stop()
        self.recording_thread.join()
        self.hi_there["text"] = "Start recording"
        self.hi_there["command"] = self.start_recording

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()
    # analyzer = ClickAnalyzer('mouse-recording.csv')
    # analyzer.analyze()
    # recorder = MouseRecorder()
    # recorder.start()

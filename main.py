from pynput.mouse import Listener, Button, Controller
from enum import Enum
import time
import csv
import statistics
import tkinter as tk
import threading
import random
import logging
from scipy import stats
import matplotlib as plt
import numpy as np


class MouseEvent(Enum):
    MOVED = 1
    LEFT_MOUSE_PRESSED = 2
    LEFT_MOUSE_RELEASED = 3
    RIGHT_MOUSE_PRESSED = 4
    RIGHT_MOUSE_RELEASED = 5
    MIDDLE_MOUSE_PRESSED = 6
    MIDDLE_MOUSE_RELEASED = 7

    @staticmethod
    def from_button(button, pressed):
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
        self.write(MouseEvent.from_button(button, pressed), x, y)

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
        self.mouse_press_dist = None
        self.time_between_click_dist = None

    def analyze(self):
        with open(self.file_path, newline='') as csvfile:
            csv_reader = csv.reader(csvfile)
            next(csv_reader)
            self.mouse_press_dist = analyze_mouse_press_duration(csv_reader)
            csvfile.seek(0)
            next(csv_reader)
            self.time_between_click_dist = analyze_time_between_clicks(csv_reader)
            print('Mouse press dist: ', self.mouse_press_dist)
            print('Sleep dist: ', self.time_between_click_dist)


def analyze_mouse_press_duration(csv_reader):
    durations = extract_mouse_press_durations(csv_reader)

    return stats.gamma.fit(durations)


def extract_mouse_press_durations(csv_reader):
    durations_ms = []
    left_mouse_down_time = None
    row = find_next_row_with_event(csv_reader, MouseEvent.LEFT_MOUSE_PRESSED)

    while row is not None:
        current_event = row[0]
        if current_event == MouseEvent.LEFT_MOUSE_RELEASED.name:
            durations_ms.append(float(row[3]) - left_mouse_down_time)
        else:
            left_mouse_down_time = float(row[3])
        is_pressed = current_event == MouseEvent.LEFT_MOUSE_PRESSED.name
        next_event_of_interest = MouseEvent.LEFT_MOUSE_RELEASED if is_pressed else MouseEvent.LEFT_MOUSE_PRESSED
        row = find_next_row_with_event(csv_reader, next_event_of_interest)

    return durations_ms


def find_next_row_with_event(csv_reader, event):
    for row in csv_reader:
        if row[0] == event.name:
            return row

    return None


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

    return stats.gamma.fit(times)


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()
        self.mouse_recorder = MouseRecorder()

    def create_widgets(self):
        self.record_button = tk.Button(self)
        self.record_button["text"] = "Start recording"
        self.record_button["command"] = self.start_recording
        self.record_button.pack(side="top")

        self.quit = tk.Button(self, text="QUIT", fg="red",
                              command=self.master.destroy)
        self.quit.pack(side="bottom")

    def start_recording(self):
        self.recording_thread = threading.Thread(target=self.mouse_recorder.start)
        self.recording_thread.start()
        self.record_button["text"] = "Stop recording"
        self.record_button["command"] = self.stop_recording

    def stop_recording(self):
        self.mouse_recorder.stop()
        self.recording_thread.join()
        self.record_button["text"] = "Start recording"
        self.record_button["command"] = self.start_recording


class AutoClicker:
    def __init__(self, mouse_press_dist, time_between_click_dist):
        self.mouse_press_dist = mouse_press_dist
        self.time_between_click_dist = time_between_click_dist
        self.is_running = False

    def start(self):
        mouse = Controller()

        self.is_running = True
        while self.is_running:
            click_duration = stats.gamma.rvs(self.mouse_press_dist[0], loc=self.mouse_press_dist[1],
                                             scale=self.mouse_press_dist[2])
            sleep_time = stats.gamma.rvs(self.time_between_click_dist[0], loc=self.time_between_click_dist[1],
                                         scale=self.time_between_click_dist[2])
            print('Left mouse down')
            mouse.press(Button.left)
            time.sleep(click_duration)
            print('Left mouse up')
            print('Sleeping for ', sleep_time, ' seconds')
            time.sleep(sleep_time)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # root = tk.Tk()
    # app = Application(master=root)
    # app.mainloop()
    analyzer = ClickAnalyzer('mouse-recording.csv')
    analyzer.analyze()
    fig, ax = plt.subplots(1, 1)
    x = l
    y1 = stats.gamma.pdf()
    # autoclicker = AutoClicker(analyzer.mouse_press_dist, analyzer.time_between_click_dist)
    # autoclicker.start()
    # recorder = MouseRecorder()
    # recorder.start()

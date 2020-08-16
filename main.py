from pynput.mouse import Listener, Button, Controller
from enum import Enum
import time
import csv
import tkinter as tk
import threading
from scipy import stats


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
        with open('mouse_recording.csv', 'w', newline='', buffering=1) as csv_file:
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
    durations = []
    left_mouse_down_time = None
    row = find_next_row_with_event(csv_reader, MouseEvent.LEFT_MOUSE_PRESSED)

    while row is not None:
        current_event = row[0]
        if current_event == MouseEvent.LEFT_MOUSE_RELEASED.name:
            durations.append(float(row[3]) - left_mouse_down_time)
        else:
            left_mouse_down_time = float(row[3])
        is_pressed = current_event == MouseEvent.LEFT_MOUSE_PRESSED.name
        next_event_of_interest = MouseEvent.LEFT_MOUSE_RELEASED if is_pressed else MouseEvent.LEFT_MOUSE_PRESSED
        row = find_next_row_with_event(csv_reader, next_event_of_interest)

    print(durations)
    return durations


def analyze_time_between_clicks(csv_reader):
    times = []
    row = find_next_row_with_event(csv_reader, MouseEvent.LEFT_MOUSE_PRESSED)
    previous_mouse_press_time = float(row[3])
    while row is not None:
        tm = float(row[3])
        times.append(tm - previous_mouse_press_time)
        previous_mouse_press_time = tm
        row = find_next_row_with_event(csv_reader, MouseEvent.LEFT_MOUSE_PRESSED)

    even_click_times = times[::2]
    odd_click_times = times[1::2]
    return stats.gamma.fit(even_click_times), stats.gamma.fit(odd_click_times)


def find_next_row_with_event(csv_reader, event):
    for row in csv_reader:
        if row[0] == event.name:
            return row

    return None


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()
        self.mouse_recorder = MouseRecorder()
        analyzer = ClickAnalyzer('mouse_recording.csv')
        analyzer.analyze()
        self.auto_alcher = AutoAlcher(analyzer.mouse_press_dist, analyzer.time_between_click_dist)

    def create_widgets(self):
        self.record_button = tk.Button(self)
        self.record_button["text"] = "Start recording"
        self.record_button["command"] = self.start_recording
        self.record_button.pack(side="top")

        self.auto_alch_button = tk.Button(self)
        self.auto_alch_button["text"] = "Start auto alcher"
        self.auto_alch_button["command"] = self.toggle_auto_alcher
        self.auto_alch_button.pack(side="top")

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

    def toggle_auto_alcher(self):
        if self.auto_alcher.is_running:
            self.auto_alcher.stop()
            self.auto_alcher_thread.join()
            self.auto_alch_button["text"] = "Start auto alcher"
        else:
            self.auto_alcher_thread = threading.Thread(target=self.auto_alcher.start)
            self.auto_alcher_thread.start()
            self.auto_alch_button["text"] = "Stop auto alcher"


class AutoAlcher:
    def __init__(self, mouse_press_dist, time_between_click_dist):
        self.mouse_press_dist = mouse_press_dist
        self.time_between_click_dist = time_between_click_dist
        self.is_running = False
        self.mouse = Controller()
        self.click_count = 0

    def start(self):
        self.is_running = True
        while self.is_running:
            self.click()
            self.wait()

    def stop(self):
        self.is_running = False
        print(f'Stopped after {self.click_count} clicks')

    def click(self):
        a, loc, beta = self.mouse_press_dist

        mouse_down_duration = stats.gamma.rvs(a, loc=loc, scale=beta)
        print(f'Left mouse click with {mouse_down_duration} duration')
        self.mouse.press(Button.left)
        time.sleep(mouse_down_duration)
        self.mouse.release(Button.left)
        self.click_count += 1

    def wait(self):
        idx = self.click_count % 2
        a, loc, beta = self.time_between_click_dist[idx]
        sleep_time = stats.gamma.rvs(a, loc=loc, scale=beta)
        print(f'Sleeping for {sleep_time} seconds')
        time.sleep(sleep_time)


if __name__ == '__main__':
    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()

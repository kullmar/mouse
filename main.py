import csv
import ctypes
import logging
import random
import threading
import time
import tkinter as tk
from abc import ABC, abstractmethod
from enum import Enum, auto

import pyautogui
import win32gui
from pynput.mouse import Listener, Button, Controller
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

    short_pauses = times[::2]
    long_pauses = times[1::2]
    return stats.gamma.fit(short_pauses), stats.gamma.fit(long_pauses)


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
        self.auto_alcher = AutoAlcher(Mouse(), analyzer.time_between_click_dist)
        self.bot = Bot()

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
            self.auto_alcher_thread = threading.Thread(target=self.auto_alcher.run)
            self.auto_alcher_thread.start()
            self.auto_alch_button["text"] = "Stop auto alcher"


class Script(ABC):
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def stop(self):
        pass


class AutoAlcher(Script):
    class State(Enum):
        CLICK_SPELL = auto()
        CLICK_ITEM = auto()
        SHORT_IDLE = auto()
        LONG_IDLE = auto()
        STOPPED = auto()

    def __init__(self, mouse, time_between_click_dist):
        super().__init__("Auto Alcher")
        self.time_between_click_dist = time_between_click_dist
        self.is_running = False
        self.click_count = 0
        self.current_state = self.State.STOPPED
        self.mouse = mouse
        self.previous_animation_started_at = None
        self.alchemy_image = './images/high_level_alchemy.png'
        self.item_image = './images/maple_longbow.png'
        self.alchemy_rect = None
        self.item_rect = None

    def run(self):
        logging.info('Starting auto alcher')
        self.is_running = True
        self.set_state(self.State.CLICK_SPELL)
        while self.is_running:
            # if not is_runelite_in_foreground():
            #     logging.info('RuneLite not in foreground. Sleeping for 5 sec')
            #     time.sleep(5)
            # else:
            self.act()

    def act(self):
        if self.current_state == self.State.CLICK_SPELL:
            if not self.alchemy_rect:
                t1 = time.perf_counter()
                logging.debug('Attempting to locate spell..')
                self.alchemy_rect = pyautogui.locateOnScreen(self.alchemy_image, grayscale=True, confidence=0.8,
                                                             region=(1500, 600, 500, 500))
                locate_tries = 1
                while not self.alchemy_rect and locate_tries < 5:
                    logging.debug(f'Failed to locate! Attempt no. {locate_tries}')
                    time.sleep(random.random())
                    self.alchemy_rect = pyautogui.locateOnScreen(self.alchemy_image, grayscale=True, confidence=0.8,
                                                                 region=(1500, 600, 500, 500))
                    locate_tries += 1

                if self.alchemy_rect:
                    delta = time.perf_counter() - t1
                    logging.debug(f'Located spell in {delta} sec')

            if self.alchemy_rect and self.mouse.is_inside(self.alchemy_rect):
                self.mouse.click()
                self.short_idle()
                self.set_state(self.State.CLICK_ITEM)

        elif self.current_state == self.State.CLICK_ITEM:
            if not self.item_rect:
                t1 = time.perf_counter()
                logging.debug('Attempting to locate item in inventory..')
                self.item_rect = pyautogui.locateOnScreen(self.item_image, grayscale=True, confidence=0.7,
                                                          region=(1500, 600, 500, 500))
                locate_tries = 1
                while not self.item_rect and locate_tries <= 5:
                    logging.debug(f'Failed to locate! Attempt no. {locate_tries}')
                    time.sleep(random.random())
                    self.item_rect = pyautogui.locateOnScreen(self.item_image, grayscale=True, confidence=0.7,
                                                              region=(1500, 600, 500, 500))
                    locate_tries += 1

                if self.item_rect:
                    delta = time.perf_counter() - t1
                    logging.debug(f'Located item in {delta} sec')

            if self.item_rect and self.mouse.is_inside(self.item_rect):
                self.mouse.click()
                self.long_idle()
                self.set_state(self.State.CLICK_SPELL)

        else:
            raise RuntimeError("Invalid state")

    def stop(self):
        self.is_running = False
        logging.info(f'Stopped after {self.click_count} clicks')
        self.click_count = 0

    def click(self):
        self.mouse.click()
        self.click_count += 1

    def short_idle(self):
        a, loc, beta = self.time_between_click_dist[0]
        sleep_time = stats.gamma.rvs(a, loc=loc, scale=beta)
        logging.debug(f'Idling for {sleep_time} sec')
        time.sleep(sleep_time)

    def long_idle(self):
        a, loc, beta = self.time_between_click_dist[1]
        sleep_time = stats.gamma.rvs(a, loc=loc, scale=beta)
        logging.debug(f'Idling for {sleep_time} sec')
        time.sleep(sleep_time)

    def set_state(self, state):
        if state != self.current_state:
            self.current_state = state
            logging.debug(f'New state: {state.name}')


def focus_window(name):
    handle = find_window(name)
    if handle:
        ctypes.windll.user32.SetForegroundWindow(handle)
        return True
    return False


def find_window(name):
    return ctypes.windll.user32.FindWindowW(None, name)


def is_runelite_in_foreground():
    user32 = ctypes.windll.user32
    h_wnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(h_wnd) + 1
    title = ctypes.create_unicode_buffer(length)
    user32.GetWindowTextW(h_wnd, title, length)

    return 'RuneLite' in title.value


class Mouse:
    def __init__(self):
        self.controller = Controller()
        analyzer = ClickAnalyzer('mouse_recording.csv')
        analyzer.analyze()
        self.mouse_press_dist = analyzer.mouse_press_dist

    def click(self):
        a, loc, beta = self.mouse_press_dist
        mouse_down_duration = stats.gamma.rvs(a, loc=loc, scale=beta)
        self.controller.press(Button.left)
        time.sleep(mouse_down_duration)
        self.controller.release(Button.left)

    def move_to(self, x, y):
        pass

    def get_position(self):
        return self.controller.position[0], self.controller.position[1]

    def is_inside(self, rect):
        x, y = self.get_position()
        return rect[0] <= x <= rect[0] + rect[2] \
               and rect[1] <= y <= rect[1] + rect[3]


class Bot:

    def __init__(self):
        self.active_script = None
        self.runelite_client = None
        self.mouse = Mouse()
        threading.Thread(target=self.init_runelite_info).start()

    def init_runelite_info(self):
        logging.info('Trying to find RuneLite..')
        window_title = 'RuneLite - megacrank'
        hwnd = win32gui.FindWindow(None, window_title)
        while not hwnd:
            time.sleep(1)
            hwnd = win32gui.FindWindow(None, window_title)
        logging.info('Runelite found!')
        self.runelite_client = {'hwnd': hwnd, 'rect': win32gui.GetWindowRect(hwnd)}

    def start_script(self):
        if self.active_script:
            logging.info(f'Starting script: {self.active_script.name}')
            self.active_script.run()

    def stop_script(self):
        if self.active_script:
            logging.info(f'Stopping script: {self.active_script.name}')
            self.active_script.stop()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    root = tk.Tk(className='Kränkbot')
    root.geometry('300x200')
    app = Application(master=root)
    app.mainloop()

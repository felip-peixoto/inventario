import tkinter as tk


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Inventário")
        self.geometry("800x600")

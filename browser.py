import sys
from request import request
from render import lex
import tkinter

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100

def layout(text):
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP
    for c in text:
        if c == '\n':
            cursor_y += VSTEP
            cursor_x = HSTEP
        else:
            display_list.append((cursor_x, cursor_y, c))
            cursor_x += HSTEP
        if cursor_x >= WIDTH - HSTEP:
            cursor_y += VSTEP
            cursor_x = HSTEP

    return display_list

class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
        self.canvas.pack()
        self.scroll = 0
        self.window.bind("<Down>", self.scrolldown)
    
    def load(self, url):
        headers, body = request(url)
        text = lex(body)
        self.display_list = layout(text)
        self.draw()
    
    def draw(self):
        self.canvas.delete("all")
        for x, y, c in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + VSTEP < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=c)
    
    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) >= 2 else "file://test.html"
    Browser().load(url)
    tkinter.mainloop()

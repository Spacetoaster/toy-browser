import sys
from request import request
from render import lex
import tkinter
import tkinter.font

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100

def layout(text, width, zoom_factor):
    display_list = []
    h_step = int(zoom_factor * HSTEP)
    v_step = int(zoom_factor * VSTEP)
    cursor_x, cursor_y = h_step, v_step
    for c in text:
        if c == '\n':
            cursor_y += v_step
            cursor_x = h_step
        else:
            display_list.append((cursor_x, cursor_y, c))
            cursor_x += h_step
        if cursor_x >= width - h_step:
            cursor_y += v_step
            cursor_x = h_step

    return display_list

class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
        self.width = WIDTH
        self.height = HEIGHT
        self.canvas.pack(expand=True, fill=tkinter.BOTH)
        self.scroll = 0
        self.zoom_factor = 1
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<MouseWheel>", self.handle_mousewheel)
        self.window.bind("<Configure>", self.handle_resize)
        self.window.bind("+", self.zoom_in)
        self.window.bind("-", self.zoom_out)

    def zoom_in(self, e):
        self.zoom_factor = self.zoom_factor + 0.25 if self.zoom_factor <= 1.75 else 2
        self.layout()
        self.draw()
    
    def zoom_out(self, e):
        self.zoom_factor = self.zoom_factor - 0.25 if self.zoom_factor > 1.25 else 1
        self.layout()
        self.draw()
    
    def load(self, url):
        headers, body = request(url)
        self.text = lex(body)
        self.layout()
        self.draw()

    def layout(self):
        self.display_list = layout(self.text, self.width, self.zoom_factor)
    
    def draw(self):
        font = tkinter.font.Font(size=int(13 * self.zoom_factor))
        v_step = int(VSTEP * self.zoom_factor)
        self.canvas.delete("all")
        for x, y, c in self.display_list:
            if y > self.scroll + self.height: continue
            if y + v_step < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=c, font=font)
        
    
    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()
    
    def scrollup(self, e):
        self.scroll = max(0, self.scroll - SCROLL_STEP)
        self.draw()
    
    def handle_mousewheel(self, e):
        # only works on mac due to how tk handles mouse wheel events
        if e.delta == 1:
            self.scrollup(e)
        elif e.delta == -1:
            self.scrolldown(e)
    
    def handle_resize(self, e):
        self.width = e.width
        self.height = e.height
        self.layout()
        self.draw()



if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) >= 2 else "file://test.html"
    Browser().load(url)
    tkinter.mainloop()

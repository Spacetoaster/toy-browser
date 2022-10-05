import sys
from request import request
from render import lex, Text, Tag
import tkinter
import tkinter.font

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100
FONTS = {}

class Layout:
    def __init__(self, tokens, width = WIDTH, height = HEIGHT):
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"
        self.size = 16
        self.line = []
        self.center = False
        self.width = width
        self.height = height
        for tok in tokens:
            self.token(tok)
        self.flush()
    
    def token(self, tok):
        if isinstance(tok, Text):
            self.text(tok)
        elif tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag == "br":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP
        elif tok.tag == "h1 class=\"title\"":
            self.center = True
        elif tok.tag == "/h1":
            self.flush()
            self.center = False
    
    def text(self, tok):
        font = self.get_font(self.size, self.weight, self.style)
        for word in tok.text.split():
            w = font.measure(word)
            if self.cursor_x + w > self.width - HSTEP:
                self.flush()
            self.line.append((self.cursor_x, word, font, w))
            self.cursor_x += w + font.measure(" ")
    
    def get_font(self, size, weight, slant):
        key = (size, weight, slant)
        if key not in FONTS:
            font = tkinter.font.Font(size=size, weight=weight, slant=slant)
            FONTS[key] = font
        return FONTS[key]

    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for x, word, font, _ in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        offset_x = 0
        if self.center:
            total_width = sum([l[3] for l in self.line])
            print(total_width)
            offset_x = (self.width - 2 * HSTEP - total_width) / 2
        for x, word, font, _ in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x + offset_x, y, word, font))
        self.cursor_x = HSTEP
        self.line = []
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent

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
        self.tokens = lex(body)
        self.layout()
        self.draw()

    def layout(self):
        self.display_list = Layout(self.tokens, self.width, self.height).display_list
    
    def draw(self):
        v_step = int(VSTEP * self.zoom_factor)
        self.canvas.delete("all")
        for x, y, c, font in self.display_list:
            if y > self.scroll + self.height: continue
            if y + v_step < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=c, font=font, anchor='nw')
        
    
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

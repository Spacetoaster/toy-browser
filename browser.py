import sys
from request import request
from parser import Text, HTMLParser, ViewSourceParser, print_tree
import tkinter
import tkinter.font

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100
FONTS = {}

class Layout:
    def __init__(self, tree, width = WIDTH, height = HEIGHT):
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
        self.superscript = False
        self.render = False
        self.pre = False
        self.recurse(tree)
        print_tree(tree)
        self.flush()
    
    def recurse(self, tree):
        if isinstance(tree, Text):
            if self.render:
                self.text(tree)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)
    
    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 4
        elif tag == "br":
            self.flush()
        elif tag == "h1":
            self.center = True
        elif tag == "sup":
            self.superscript = True
        elif tag == "body":
            self.render = True
        elif tag == "pre":
            self.flush()
            self.pre = True
    
    def close_tag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "small":
            self.size += 2
        elif tag == "big":
            self.size -= 4
        elif tag == "p":
            self.flush()
            self.cursor_y += VSTEP
        elif tag == "h1":
            self.flush()
            self.center = False
        elif tag == "sup":
            self.superscript = False
        elif tag == "body":
            self.render = False
        elif tag == "pre":
            self.flush()
            self.pre = False

    def text(self, tok):
        font = self.get_font(self.size, self.weight, self.style)
        if self.superscript:
            font = self.get_font(int(self.size / 2), self.weight, self.style)
        elif self.pre:
            font = self.get_font(self.size, self.weight, self.style, "Courier New")
            for c in tok.text:
                if c == "\n":
                    self.flush()
                w = font.measure(c)
                self.line.append((self.cursor_x, c, font, w, self.superscript))
                self.cursor_x += w
        else:
            for word in tok.text.split():
                w = font.measure(word)
                if self.word_fits_line(w):
                    self.line.append((self.cursor_x, word, font, w, self.superscript))
                    self.cursor_x += w + font.measure(" ")
                else:
                    self.wrap_word(font, word)
            

    def wrap_word(self, font, word):
                word_splits = word.split("\N{soft hyphen}")
                l = 0
                r = len(word_splits)
                while l < len(word_splits):
                    prefix = "".join(word_splits[l:r])
                    w_prefix = font.measure(prefix)
                    while not self.word_fits_line(w_prefix) and r > l:
                        # shorten prefix until it fits in the current line or is empty
                        r -= 1
                        prefix = "".join(word_splits[l:r]) + "-"
                        w_prefix = font.measure(prefix)
                    if prefix != "-":
                        self.line.append((self.cursor_x, prefix, font, font.measure(prefix), self.superscript))
                        self.cursor_x += font.measure(prefix) + font.measure(" ")
                    elif len(self.line) == 0:
                        # if all prefixes of the word are longer than the line width, append the smallest prefix
                        r = l + 1
                        prefix = "".join(word_splits[l:r])
                        self.line.append((self.cursor_x, prefix, font, font.measure(prefix), self.superscript))
                        self.cursor_x += font.measure(prefix) + font.measure(" ")
                    if r < len(word_splits):
                        # do not flush after the whole word has been processed
                        self.flush()
                    l = r
                    r = len(word_splits)

    
    def word_fits_line(self, word_width):
        return self.cursor_x + word_width <= self.width - HSTEP
    
    def get_font(self, size, weight, slant, family = None):
        key = (size, weight, slant, family)
        if key not in FONTS:
            if family:
                font = tkinter.font.Font(size=size, weight=weight, slant=slant, family=family)
            else:    
                font = tkinter.font.Font(size=size, weight=weight, slant=slant)
            FONTS[key] = font
        return FONTS[key]

    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for _, _, font, _, _ in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        offset_x = 0
        if self.center:
            total_width = sum([l[3] for l in self.line])
            offset_x = (self.width - 2 * HSTEP - total_width) / 2
        for x, word, font, _, superscript in self.line:
            ascent = font.metrics("ascent")
            if superscript:
                ascent *= 2
            y = baseline - ascent
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
        headers, body, view_source = request(url)
        if view_source:
            self.nodes = ViewSourceParser(body).parse()
        else:
            self.nodes = HTMLParser(body).parse()
        self.layout()
        self.draw()

    def layout(self):
        if self.width > 1 and self.height > 1:
            self.display_list = Layout(self.nodes, self.width, self.height).display_list
    
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

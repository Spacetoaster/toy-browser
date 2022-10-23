import sys
from request import request
from parser import Element, Text, HTMLParser, ViewSourceParser, print_tree
import tkinter
import tkinter.font

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100
FONTS = {}

class DrawText:
    def __init__(self, x1, y1, text, font):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.bottom = y1 + font.metrics("linespace")
    
    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left, self.top - scroll,
            text=self.text,
            font=self.font,
            anchor='nw'
        )

class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color
    
    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.left, self.top - scroll,
            self.right, self.bottom - scroll,
            width=0,
            fill=self.color,
        )

class InlineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        self.display_list = []
        self.cursor_x = self.x
        if isinstance(self.node, Element) and self.node.tag == "li":
            self.cursor_x += 20
        self.cursor_y = self.y
        self.weight = "normal"
        self.style = "roman"
        self.size = 16
        self.line = []
        self.center = False
        self.superscript = False
        self.pre = False
        self.recurse(self.node)
        self.flush()
        self.height = self.cursor_y - self.y
    
    def paint(self, display_list):
        if isinstance(self.node, Element) and self.node.tag == "li":
            x1, y1 = self.x, self.y + 10
            x2, y2 = x1 + 5, y1 + 5
            display_list.append(DrawRect(x1, y1, x2, y2, "black"))
        # chapter 5 exercise, maybe remove later
        if isinstance(self.node, Element) and self.node.tag == "nav":
            if 'class' in self.node.attributes and self.node.attributes['class'] == 'links':
                x2, y2 = self.x + self.width, self.y + self.height
                rect = DrawRect(self.x, self.y, x2, y2, "lightgray")
                display_list.append(rect)
        if isinstance(self.node, Element) and self.node.tag == "pre":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, "gray")
            display_list.append(rect)
        for x, y, word, font in self.display_list:
            display_list.append(DrawText(x, y, word, font))
    
    def recurse(self, tree):
        if isinstance(tree, Text):
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
        self.cursor_x = self.x
        self.line = []
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent

class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = node
        self.children = []
    
    def layout(self):
        self.width = WIDTH - 2 * HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child = BlockLayout(self.node, self, None)
        self.children.append(child)
        child.layout()
        self.height = child.height + 2 * VSTEP
    
    def paint(self, display_list):
        self.children[0].paint(display_list)

BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
]

def layout_mode(node):
    if isinstance(node, Text):
        return "inline"
    elif node.children:
        for child in node.children:
            if isinstance(child, Text): continue
            if child.tag in BLOCK_ELEMENTS:
                return "block"
        return "inline"
    else:
        return "block"

class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
    
    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        previous = None
        for child in self.node.children:
            if isinstance(child, Element) and child.tag == "head": continue
            if layout_mode(child) == "inline":
                next = InlineLayout(child, self, previous)
            else:
                next = BlockLayout(child, self, previous)
            self.children.append(next)
            previous = next
        for child in self.children:
            child.layout()
        self.height = sum([child.height for child in self.children])
    
    def paint(self, display_list):
        for child in self.children:
            child.paint(display_list)

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
        # self.layout()
        self.draw()
    
    def zoom_out(self, e):
        self.zoom_factor = self.zoom_factor - 0.25 if self.zoom_factor > 1.25 else 1
        # self.layout()
        self.draw()
    
    def load(self, url):
        headers, body, view_source = request(url)
        if view_source:
            self.nodes = ViewSourceParser(body).parse()
        else:
            self.nodes = HTMLParser(body).parse()
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        self.document.paint(self.display_list)
        self.draw()

    # def layout(self):
        # if self.width > 1 and self.height > 1:
        #     self.display_list = InlineLayout(self.nodes, self.width, self.height).display_list
    
    def draw(self):
        self.canvas.delete("all")
        for cmd in self.display_list:
            if cmd.top > self.scroll + self.height: continue
            if cmd.bottom < self.scroll: continue
            cmd.execute(self.scroll, self.canvas)
    
    def scrolldown(self, e):
        max_y = self.document.height - self.height
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
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
        if e.width > 1 and e.height > 1:
            self.width = e.width
            self.height = e.height
        # self.layout()
        self.draw()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) >= 2 else "file://test.html"
    Browser().load(url)
    tkinter.mainloop()

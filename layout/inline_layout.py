from constants import VSTEP, HSTEP
from parser import Element, Text
import tkinter.font

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
    def __init__(self, nodes, parent, previous):
        self.nodes = nodes
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
        if len(self.nodes) == 1:
            if isinstance(self.nodes[0], Element) and self.nodes[0].tag == "li":
                self.cursor_x += 20
        self.cursor_y = self.y
        self.weight = "normal"
        self.style = "roman"
        self.size = 16
        self.line = []
        self.center = False
        self.superscript = False
        self.pre = False
        for node in self.nodes:
            self.recurse(node)
        self.flush()
        self.height = self.cursor_y - self.y
    
    def paint(self, display_list):
        if len(self.nodes) == 1:
            node = self.nodes[0]
            bgcolor = "transparent"
            if isinstance(node, Element):
                bgcolor = node.style.get("background-color", "transparent")
            if bgcolor != "transparent":
                x2, y2 = self.x + self.width, self.y + self.height
                rect = DrawRect(self.x, self.y, x2, y2, bgcolor)
                display_list.append(rect)
            # chapter 5 exercise, remove later
            if isinstance(node, Text) and node.text == "Table of Contents":
                x2, y2 = self.x + self.width, self.y + self.height
                rect = DrawRect(self.x, self.y, x2, y2, "gray")
                display_list.append(rect)
            if isinstance(node, Element) and node.tag == "li":
                x1, y1 = self.x, self.y + 10
                x2, y2 = x1 + 5, y1 + 5
                display_list.append(DrawRect(x1, y1, x2, y2, "black"))
            # chapter 5 exercise, maybe remove later
            if isinstance(node, Element) and node.tag == "nav":
                if 'class' in node.attributes and node.attributes['class'] == 'links':
                    x2, y2 = self.x + self.width, self.y + self.height
                    rect = DrawRect(self.x, self.y, x2, y2, "lightgray")
                    display_list.append(rect)
            # if isinstance(node, Element) and node.tag == "pre":
            #     x2, y2 = self.x + self.width, self.y + self.height
            #     rect = DrawRect(self.x, self.y, x2, y2, "gray")
            #     display_list.append(rect)
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
        elif tag == "h6":
            self.style = "italic"
            self.weight = "bold"
    
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
        elif tag == "h6":
            self.style = "roman"
            self.weight = "normal"

    def text(self, tok):
        font = self.get_font(self.size, self.weight, self.style)
        if self.superscript:
            font = self.get_font(int(self.size / 2), self.weight, self.style)
        if self.pre:
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
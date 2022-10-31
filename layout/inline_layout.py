from constants import VSTEP, HSTEP
from parser import Element, Text
import tkinter.font
from .drawing import DrawRect, DrawText

FONTS = {}

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
        for x, y, word, font, color in self.display_list:
            display_list.append(DrawText(x, y, word, font, color))
    
    def recurse(self, node):
        if isinstance(node, Text):
            self.text(node)
        else:
            if node.tag == "br":
                self.flush()
            # keep special handling for pre and sup for now
            if node.tag == "pre":
                self.pre = True
            if node.tag == "sup":
                self.superscript = True
            for child in node.children:
                self.recurse(child)
            if node.tag == "pre":
                self.pre = False
            if node.tag == "sup":
                self.superscript = False

    def text(self, node):
        color = node.style["color"]
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        family = node.style["font-family"]
        if style == "normal": style = "roman"
        size = int(float(node.style["font-size"][:-2]) * 0.75)
        font = self.get_font(size, weight, style, family)
        if self.superscript:
            font = self.get_font(int(size / 2), weight, style, family)
        if self.pre:
            for c in node.text:
                if c == "\n":
                    self.flush()
                w = font.measure(c)
                self.line.append((self.cursor_x, c, font, w, color, self.superscript))
                self.cursor_x += w
        else:
            for word in node.text.split():
                w = font.measure(word)
                if self.word_fits_line(w):
                    self.line.append((self.cursor_x, word, font, w, color, self.superscript))
                    self.cursor_x += w + font.measure(" ")
                else:
                    self.wrap_word(font, word, color)
            

    def wrap_word(self, font, word, color):
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
                self.line.append((self.cursor_x, prefix, font, font.measure(prefix), color, self.superscript))
                self.cursor_x += font.measure(prefix) + font.measure(" ")
            elif len(self.line) == 0:
                # if all prefixes of the word are longer than the line width, append the smallest prefix
                r = l + 1
                prefix = "".join(word_splits[l:r])
                self.line.append((self.cursor_x, prefix, font, font.measure(prefix), color, self.superscript))
                self.cursor_x += font.measure(prefix) + font.measure(" ")
            if r < len(word_splits):
                # do not flush after the whole word has been processed
                self.flush()
            l = r
            r = len(word_splits)

    def word_fits_line(self, word_width):
        return self.cursor_x + word_width <= self.x + self.width
    
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
        metrics = [font.metrics() for _, _, font, _, _, _ in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        offset_x = 0
        if self.center:
            total_width = sum([l[3] for l in self.line])
            offset_x = (self.width - 2 * HSTEP - total_width) / 2
        for x, word, font, _, color, superscript in self.line:
            ascent = font.metrics("ascent")
            if superscript:
                ascent *= 2
            y = baseline - ascent
            self.display_list.append((x + offset_x, y, word, font, color))
        self.cursor_x = self.x
        self.line = []
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent
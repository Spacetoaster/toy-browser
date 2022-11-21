from parser import Element, Text
import tkinter.font
from .drawing import DrawRect, DrawText

FONTS = {}

visited_urls = {}

def get_font(size, weight, slant, family = None):
    key = (size, weight, slant, family)
    if key not in FONTS:
        if family:
            font = tkinter.font.Font(size=size, weight=weight, slant=slant, family=family)
        else:    
            font = tkinter.font.Font(size=size, weight=weight, slant=slant)
        FONTS[key] = font
    return FONTS[key]

class LineLayout:
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
        
        for word in self.children:
            word.layout()
        # assert len(self.children) > 0, "LineLayout without children"
        if len(self.children) == 0:
            self.height = 0
            return
        max_ascent = max([word.font.metrics("ascent") for word in self.children])
        baseline = self.y + 1.25 * max_ascent
        for word in self.children:
            word.y = baseline - word.font.metrics("ascent")
        max_descent = max([word.font.metrics("descent") for word in self.children])
        self.height = 1.25 * (max_ascent + max_descent)
    
    def paint(self, display_list):
        for child in self.children:
            child.paint(display_list)

class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.children = []
        self.parent = parent
        self.previous = previous
    
    def layout(self):
        weight = self.node.style["font-weight"] 
        style = self.node.style["font-style"]
        family = self.node.style["font-family"]
        if style == "normal": style = "roman"
        size = int(float(self.node.style["font-size"][:-2]) * 0.75)
        self.font = get_font(size, weight, style, family)
        self.width = self.font.measure(self.word)

        if self.previous:
            space = self.previous.font.measure(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x
        
        self.height = self.font.metrics("linespace")
    
    def paint(self, display_list):
        color = self.node.style["color"]
        if self.node.parent.tag == "a" and self.node.parent.attributes.get("href") in visited_urls:
            color = "#84a"
        display_list.append(DrawText(self.x, self.y, self.word, self.font, color))

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
        self.new_line()
        self.recurse(self.node)
        for line in self.children:
            line.layout()
        self.height = sum([line.height for line in self.children])
    
    def paint(self, display_list):
        bgcolor = "transparent"
        if isinstance(self.node, Element):
            bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, bgcolor)
            display_list.append(rect)
        # chapter 5 exercise, maybe remove later
        if isinstance(self.node, Element) and self.node.tag == "nav":
            if 'class' in self.node.attributes and self.node.attributes['class'] == 'links':
                x2, y2 = self.x + self.width, self.y + self.height
                rect = DrawRect(self.x, self.y, x2, y2, "lightgray")
                display_list.append(rect)
        for child in self.children:
            child.paint(display_list)
    
    def recurse(self, node):
        if isinstance(node, Text):
            self.text(node)
        else:
            if node.tag == "br":
                self.new_line()
            for child in node.children:
                self.recurse(child)

    def text(self, node):
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        family = node.style["font-family"]
        if style == "normal": style = "roman"
        size = int(float(node.style["font-size"][:-2]) * 0.75)
        font = get_font(size, weight, style, family)
        for word in node.text.split():
            w = font.measure(word)
            # don't create a new line if the line is empty, but the word still doesn't fit
            if not self.word_fits_line(w) and len(self.children[-1].children) > 0:
                self.new_line()
            line = self.children[-1]
            text = TextLayout(node, word, line, self.previous_word)
            line.children.append(text)
            self.previous_word = text
            self.cursor_x += w + font.measure(" ")                
    
    def new_line(self):
        self.previous_word = None
        self.cursor_x = self.x
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)
        self.children.append(new_line)

    def word_fits_line(self, word_width):
        return self.cursor_x + word_width <= self.x + self.width
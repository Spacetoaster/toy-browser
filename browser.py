import sys
from request import request
from parser import HTMLParser, ViewSourceParser, print_tree, Element
import tkinter
import tkinter.font
from layout.document_layout import DocumentLayout
from constants import SCROLL_STEP, HEIGHT, WIDTH

class CSSParser:
    def __init__(self, s):
        self.s = s
        self.i = 0
    
    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1
    
    def word(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        assert self.i > start
        return self.s[start:self.i]
    
    def literal(self, literal):
        assert self.i < len(self.s) and self.s[self.i] == literal
        self.i += 1
    
    def pair(self):
        prop = self.word()
        self.whitespace()
        self.literal(":")
        self.whitespace()
        val = self.word()
        return prop.lower(), val
    
    def body(self):
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            # remove try block when debugging
            try:
                prop, val = self.pair()
                pairs[prop.lower()] = val
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except AssertionError:
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs
    
    def ignore_until(self, chars):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1
    
    def selector(self):
        out = TagSelector(self.word().lower())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{":
            tag = self.word()
            descendant = TagSelector(tag.lower())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out
    
    def parse(self):
        rules = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                rules.append((selector, body))
            except AssertionError:
                why = self.ignore_until(["}"])
                if why == "}":
                    self.literal("}")
                    self.whitespace()
                else:
                    break
        return rules

def style(node, rules):
        node.style = {}
        for child in node.children:
            style(child, rules)
        for selector, body in rules:
            if not selector.matches(node): continue
            for property, value in body.items():
                node.style[property] = value
        if isinstance(node, Element) and "style" in node.attributes:
            pairs = CSSParser(node.attributes["style"]).body()
            for property, value in pairs.items():
                node.style[property] = value

class TagSelector:
    def __init__(self, tag):
        self.tag = tag
    
    def matches(self, node):
        return isinstance(node, Element) and self.tag == node.tag

class DescendantSelector:
    def __init__(self, ancestor, descendant):
        self.ancestor = ancestor
        self.descendant = descendant
    
    def matches(self, node):
        if not self.descendant.matches(node): return False
        while node.parent:
            if self.ancestor.matches(node.parent): return True
            node = node.parent
        return False

def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list

def resolve_url(url, current):
    if "://" in url:
        return url
    elif url.startswith("/"):
        scheme, hostpath = current.split("://", 1)
        host, oldpath = hostpath.split("/", 1)
        return scheme + "://" + host + url
    else:
        dir, _ = current.rsplit("/", 1)
        while url.startswith("../"):
            url = url[3:]
            if dir.count("/") == 2: continue
            dir, _ = dir.rsplit("/", 1)
        return dir + "/" + url

class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
        self.width = WIDTH
        self.height = HEIGHT
        self.canvas.pack(expand=True, fill=tkinter.BOTH)
        self.scroll = 0
        with open("browser.css") as f:
            self.default_style_sheet = CSSParser(f.read()).parse()
        self.zoom_factor = 1
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<MouseWheel>", self.handle_mousewheel)
        self.window.bind("<Configure>", self.handle_resize)
        # self.window.bind("+", self.zoom_in)
        # self.window.bind("-", self.zoom_out)

    # def zoom_in(self, e):
    #     self.zoom_factor = self.zoom_factor + 0.25 if self.zoom_factor <= 1.75 else 2
    #     self.draw()
    
    # def zoom_out(self, e):
    #     self.zoom_factor = self.zoom_factor - 0.25 if self.zoom_factor > 1.25 else 1
    #     self.draw()
    
    def load(self, url):
        headers, body, view_source = request(url)
        if view_source:
            self.nodes = ViewSourceParser(body).parse()
        else:
            self.nodes = HTMLParser(body).parse()
        # print_tree(self.nodes)
        rules = self.default_style_sheet.copy()
        links = [node.attributes["href"] for node in tree_to_list(self.nodes, [])
                if isinstance(node, Element) and node.tag == "link" and "href" in node.attributes
                and node.attributes.get("rel") == "stylesheet"]
        for link in links:
            try:
                header, body, _ = request(resolve_url(link, url))
                print("downloaded stylesheet {}".format(link))
            except:
                print("error downloading stylesheet {}".format(link))
                continue
            rules.extend(CSSParser(body).parse())
        style(self.nodes, rules)
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        self.document.paint(self.display_list)
        self.draw()
    
    def draw(self):
        self.canvas.delete("all")
        for cmd in self.display_list:
            if cmd.top > self.scroll + self.height: continue
            if cmd.bottom < self.scroll: continue
            cmd.execute(self.scroll, self.canvas)
        self.drawScrollbar()
    
    def drawScrollbar(self):
        show_scrollbar = self.document.height > self.height
        if not show_scrollbar:
            return
        scrollbar_height = (self.height / self.document.height) * self.height
        scrollbar_offset = (self.scroll / self.document.height) * self.height 
        self.canvas.create_rectangle(
            self.width - 8, scrollbar_offset,
            self.width, scrollbar_offset + scrollbar_height,
            width=0,
            fill="white",
        )
    
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
        self.document.layout(self.width)
        self.display_list = []
        self.document.paint(self.display_list)
        self.draw()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) >= 2 else "file://test.html"
    Browser().load(url)
    tkinter.mainloop()

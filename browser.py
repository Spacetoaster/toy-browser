import sys
from request import request
from parser import HTMLParser, ViewSourceParser, print_tree, Element, Text
import tkinter
import tkinter.font
from layout.document_layout import DocumentLayout
from constants import SCROLL_STEP, HEIGHT, WIDTH
from style import CSSParser, style, cascade_priority

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
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT, bg="white")
        self.width = WIDTH
        self.height = HEIGHT
        self.canvas.pack(expand=True, fill=tkinter.BOTH)
        self.scroll = 0
        self.url = None
        with open("browser.css") as f:
            self.default_style_sheet = CSSParser(f.read()).parse()
        self.zoom_factor = 1
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<MouseWheel>", self.handle_mousewheel)
        self.window.bind("<Configure>", self.handle_resize)
        self.window.bind("<Button-1>", self.click)
        # self.window.bind("+", self.zoom_in)
        # self.window.bind("-", self.zoom_out)

    # def zoom_in(self, e):
    #     self.zoom_factor = self.zoom_factor + 0.25 if self.zoom_factor <= 1.75 else 2
    #     self.draw()
    
    # def zoom_out(self, e):
    #     self.zoom_factor = self.zoom_factor - 0.25 if self.zoom_factor > 1.25 else 1
    #     self.draw()
    
    def load(self, url):
        self.url = url
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
        inline_styles = [node for node in tree_to_list(self.nodes, []) if isinstance(node, Element) and node.tag == "style"]
        for node in inline_styles:
            assert len(node.children) == 1, "Inline style with multiple text nodes"
            rules.extend(CSSParser(node.children[0].text).parse())
        style(self.nodes, sorted(rules, key=cascade_priority))
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
            fill="#333",
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
    
    def click(self, e):
        x, y = e.x, e.y
        y += self.scroll
        objs = [obj for obj in tree_to_list(self.document, [])
                if obj.x <= x < obj.x + obj.width
                and obj.y <= y < obj.y + obj.height]
        if not objs: return
        elt = objs[-1].node
        while elt:
            if isinstance(elt, Text):
                pass
            elif elt.tag == "a" and "href" in elt.attributes:
                url = resolve_url(elt.attributes["href"], self.url)
                return self.load(url)
            elt = elt.parent

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) >= 2 else "file://test.html"
    Browser().load(url)
    tkinter.mainloop()

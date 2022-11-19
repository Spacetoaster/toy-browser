import sys
from layout.inline_layout import get_font
from request import request
from parser import HTMLParser, ViewSourceParser, print_tree, Element, Text
import tkinter
import tkinter.font
from layout.document_layout import DocumentLayout
from constants import CHROME_PX, SCROLL_STEP, HEIGHT, WIDTH
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

class Tab:
    def __init__(self):
        with open("browser.css") as f:
            self.default_style_sheet = CSSParser(f.read()).parse()
        self.scroll = 0
        self.history = []
        self.future = []
    
    def load(self, url, back_or_forward=False):
        self.history.append(url)
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
        self.scroll = 0
        if not back_or_forward:
            self.future = []
    
    def go_back(self):
        if len(self.history) > 1:
            forward = self.history.pop()
            self.future.append(forward)
            back = self.history.pop()
            self.load(back, back_or_forward=True)
    
    def go_forward(self):
        if len(self.future) > 0:
            self.load(self.future.pop(0), back_or_forward=True)
    
    def scrolldown(self, height):
        max_y = self.document.height - (height - CHROME_PX)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
    
    def scrollup(self):
        self.scroll = max(0, self.scroll - SCROLL_STEP)
    
    def click(self, x, y, load = True):
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
                if load:
                    return self.load(url)
                else:
                    return url
            elt = elt.parent
    
    def draw(self, canvas, width, height):
        for cmd in self.display_list:
            if cmd.top > self.scroll + height - CHROME_PX: continue
            if cmd.bottom < self.scroll: continue
            cmd.execute(self.scroll - CHROME_PX, canvas)
        self.drawScrollbar(canvas, width, height)
    
    def drawScrollbar(self, canvas, width, height):
        max_scroll = self.document.height - (height - CHROME_PX)
        page_height = height - CHROME_PX
        show_scrollbar = self.document.height > page_height
        if not show_scrollbar:
            return
        scrollbar_height = (page_height / self.document.height) * page_height
        scrollbar_offset = (self.scroll / self.document.height) * page_height + CHROME_PX
        canvas.create_rectangle(
            width - 8, scrollbar_offset,
            width, scrollbar_offset + scrollbar_height,
            width=0,
            fill="#333",
        )
    
    def resize(self, width):
        self.document.layout(width)
        self.display_list = []
        self.document.paint(self.display_list)

class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT, bg="white")
        self.width = WIDTH
        self.height = HEIGHT
        self.canvas.pack(expand=True, fill=tkinter.BOTH)
        self.zoom_factor = 1
        self.tabs = []
        self.active_tab = None
        self.focus = None
        self.address_bar = ""
        self.window.bind("<Down>", self.handle_down)
        self.window.bind("<Up>", self.handle_up)
        self.window.bind("<MouseWheel>", self.handle_mousewheel)
        self.window.bind("<Configure>", self.handle_resize)
        self.window.bind("<Button-1>", self.handle_click)
        self.window.bind("<Button-2>", self.handle_middle_click)
        self.window.bind("<Key>", self.handle_key)
        self.window.bind("<Return>", self.handle_enter)
        self.window.bind("<BackSpace>", self.handle_backspace)
    
    def draw(self):
        self.canvas.delete("all")
        # draw page content
        self.tabs[self.active_tab].draw(self.canvas, self.width, self.height)
        # draw tabs
        self.canvas.create_rectangle(0, 0, self.width, CHROME_PX, fill="white", outline="black")
        tabfont = get_font(20, "normal", "roman")
        for i, tab in enumerate(self.tabs):
            name = "Tab {}".format(i)
            x1, x2 = 40 + 80 * i, 120 + 80 * i
            self.canvas.create_line(x1, 0, x1, 40, fill="black")
            self.canvas.create_line(x2, 0, x2, 40, fill="black")
            self.canvas.create_text(x1 + 10, 10, anchor="nw", text=name, font=tabfont, fill="black")
            if i == self.active_tab:
                self.canvas.create_line(0, 40, x1, 40, fill="black")
                self.canvas.create_line(x2, 40, self.width, 40, fill="black")
            buttonfont = get_font(30, "normal", "roman")
            self.canvas.create_rectangle(10, 10, 30, 30, outline="black", width=1)
            self.canvas.create_text(11, 0, anchor="nw", text="+", font=buttonfont, fill="black")
        # draw address bar
        self.canvas.create_rectangle(70, 50, self.width - 10, 90, outline="black", width=1)
        if self.focus == "address bar":
            self.canvas.create_text(85, 55, anchor="nw", text=self.address_bar, font=buttonfont, fill="black")
            w = buttonfont.measure(self.address_bar)
            self.canvas.create_line(85 + w, 55, 85 + w, 85, fill="black")
        else:
            url = self.tabs[self.active_tab].url
            self.canvas.create_text(85, 55, anchor="nw", text=url, font=buttonfont, fill="black")
        # draw back button
        back_color = "black" if len(self.tabs[self.active_tab].history) > 1 else "lightgray"
        self.canvas.create_rectangle(10, 50, 35, 90, outline="black", width=1)
        self.canvas.create_polygon(15, 70, 30, 55, 30, 85, fill=back_color)
        # draw forward button
        forward_color = "black" if len(self.tabs[self.active_tab].future) > 0 else "lightgray"
        self.canvas.create_rectangle(40, 50, 65, 90, outline="black", width=1)
        self.canvas.create_polygon(45, 55, 60, 70, 45, 85, fill=forward_color)

    def handle_down(self, e):
        self.tabs[self.active_tab].scrolldown(self.height)
        self.draw()
    
    def handle_up(self, e):
        self.tabs[self.active_tab].scrollup()
        self.draw()
    
    def handle_mousewheel(self, e):
        # only works on mac due to how tk handles mouse wheel events
        if e.delta == 1:
            self.handle_up(e)
        elif e.delta == -1:
            self.handle_down(e)
    
    def handle_resize(self, e):
        if e.width > 1 and e.height > 1:
            self.width = e.width
            self.height = e.height
        self.tabs[self.active_tab].resize(self.width)
        self.draw()
    
    def handle_click(self, e):
        if e.y < CHROME_PX:
            if 40 <= e.x < 40 + 80 * len(self.tabs) and 0 <= e.y < 40:
                self.active_tab = int((e.x - 40) / 80)
            elif 10 <= e.x < 30 and 10 <= e.y < 30:
                self.load("https://browser.engineering/")
            elif 10 <= e.x < 35 and 50 <= e.y < 90:
                self.tabs[self.active_tab].go_back()
            elif 40 <= e.x < 65 and 50 <= e.y < 90:
                self.tabs[self.active_tab].go_forward()
            elif 80 <= e.x < self.width - 10 and 40 <= e.y < 90:
                self.focus = "address bar"
                self.address_bar = ""
        else:
            self.tabs[self.active_tab].click(e.x, e.y - CHROME_PX)
        self.draw()
    
    def handle_middle_click(self, e):
        if e.y >= CHROME_PX:
            url = self.tabs[self.active_tab].click(e.x, e.y - CHROME_PX, load=False)
            new_tab = Tab()
            new_tab.load(url)
            self.active_tab = len(self.tabs)
            self.tabs.append(new_tab)
            self.draw()
    
    def handle_key(self, e):
        if len(e.char) == 0: return
        if not (0x20 <= ord(e.char) < 0x7f): return

        if self.focus == "address bar":
            self.address_bar += e.char
            self.draw()
    
    def handle_enter(self, e):
        if self.focus == "address bar":
            self.tabs[self.active_tab].load(self.address_bar)
            self.focus = None
            self.draw()
    
    def handle_backspace(self, e):
        if self.focus == "address bar":
            self.address_bar = self.address_bar[:-1]
            self.draw()
    
    def load(self, url):
        new_tab = Tab()
        new_tab.load(url)
        self.active_tab = len(self.tabs)
        self.tabs.append(new_tab)
        self.draw()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) >= 2 else "file://test.html"
    Browser().load(url)
    tkinter.mainloop()

import sys
from helpers import resolve_url, tree_to_list
from layout.inline_layout import get_font, visited_urls, InputLayout
from request import request
from parser import HTMLParser, ViewSourceParser, print_tree, Element, Text
import tkinter
import tkinter.font
from tkinter.messagebox import askyesno
from layout.document_layout import DocumentLayout
from constants import CHROME_PX, SCROLL_STEP, HEIGHT, WIDTH
from style import CSSParser, style, cascade_priority
import urllib.parse
import dukpy

def handle_special_pages(url, browser):
    if url == "about:bookmarks":
        body = "<html><body><h1>Bookmarks</h1>"
        for bookmark in browser.bookmarks:
            body += "<a href=\"{}\"><li>{}</li>".format(bookmark, bookmark)
        body += "</body></html>"
        return None, body, False
    return None, None, False

EVENT_DISPATCH_CODE = "new Node(dukpy.handle).dispatchEvent(new Event(dukpy.type))"

class JSContext:
    def __init__(self, tab):
        self.tab = tab
        self.interp = dukpy.JSInterpreter()
        self.interp.export_function("log", print)
        self.interp.export_function("querySelectorAll", self.querySelectorAll)
        self.interp.export_function("getAttribute", self.getAttribute)
        self.interp.export_function("innerHTML_set", self.innerHTML_set)
        self.interp.export_function("children", self.children)
        with open("runtime.js") as f:
            self.interp.evaljs(f.read())
        self.node_to_handle = {}
        self.handle_to_node = {}

    def run(self, code):
        return self.interp.evaljs(code)

    def get_handle(self, elt):
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle)
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
        else:
            handle = self.node_to_handle[elt]
        return handle

    def querySelectorAll(self, selector_text):
        selector = CSSParser(selector_text).selector()
        nodes = [node for node in tree_to_list(self.tab.nodes, []) if selector.matches(node)]
        return [self.get_handle(node) for node in nodes]
    
    def getAttribute(self, handle, attr):
        elt = self.handle_to_node[handle]
        return elt.attributes.get(attr, None)
    
    def dispatch_event(self, type, elt):
        handle = self.node_to_handle.get(elt, -1)
        do_default = self.interp.evaljs(EVENT_DISPATCH_CODE, type=type, handle=handle)
        return not do_default
    
    def innerHTML_set(self, handle, s):
        doc = HTMLParser("<html><body>" + s + "</body></html>").parse()
        new_nodes = doc.children[0].children
        elt = self.handle_to_node[handle]
        elt.children = new_nodes
        for child in elt.children:
            child.parent = elt
        self.tab.render()

    def children(self, handle):
        elt = self.handle_to_node[handle]
        handles = [self.get_handle(child) for child in elt.children if isinstance(child, Element)]
        return handles

class Tab:
    def __init__(self, browser):
        with open("browser.css") as f:
            self.default_style_sheet = CSSParser(f.read()).parse()
        self.scroll = 0
        self.history = []
        self.future = []
        self.url = ""
        self.browser = browser
        self.rules = None
        self.nodes = None
        self.focus = None
    
    def load(self, url, back_or_forward=False, req_body=None):
        only_fragment_changed = self.url != None and self.url.split("#")[0] == url.split("#")[0] and req_body == None
        self.history.append((url, req_body))
        self.url = url
        if only_fragment_changed:
            self.scroll_to_fragment(url)
        else:
            headers, body, view_source = handle_special_pages(url, self.browser)
            if not body:
                headers, body, view_source = request(url, payload=req_body)
            if view_source:
                self.nodes = ViewSourceParser(body).parse()
            else:
                self.nodes = HTMLParser(body).parse()
            # print_tree(self.nodes)
            scripts = [node.attributes["src"] for node in tree_to_list(self.nodes, [])
                       if isinstance(node, Element) and node.tag == "script"
                       and "src" in node.attributes]
            self.js = JSContext(self)
            for script in scripts:
                header, body, _ = request(resolve_url(script, url))
                try:
                    self.js.run(body)
                except dukpy.JSRuntimeError as e:
                    print("Script", script, "crashed", e)
            self.rules = self.default_style_sheet.copy()
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
                self.rules.extend(CSSParser(body).parse())
            inline_styles = [node for node in tree_to_list(self.nodes, []) if isinstance(node, Element) and node.tag == "style"]
            for node in inline_styles:
                if node.children:
                    self.rules.extend(CSSParser(node.children[0].text).parse())
            self.render()
            self.scroll = 0
            self.scroll_to_fragment(url)
        if not back_or_forward:
            self.future = []
    
    def render(self):
        style(self.nodes, sorted(self.rules, key=cascade_priority))
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        self.document.paint(self.display_list)
    
    def go_back(self):
        if len(self.history) > 1:
            _, last_body = self.history[-1]
            if last_body:
                confirmed = self.confirm_form_resubmission()
                if not confirmed:
                    return
            forward = self.history.pop()
            self.future.append(forward)
            back_url, back_body = self.history.pop()
            self.load(back_url, back_or_forward=True, req_body=back_body)

    def go_forward(self):
        if len(self.future) > 0:
            _, next_body = self.future[-1]
            if next_body:
                confirmed = self.confirm_form_resubmission()
                if not confirmed:
                    return
            next_url, next_body = self.future.pop()
            self.load(next_url, back_or_forward=True, req_body=next_body)

    def confirm_form_resubmission(self):
        return askyesno(title="Confirm form resubmission", message="Re-submitting post data, do you want to continue?")
    
    def scrolldown(self):
        max_y = self.document.height - (self.browser.height - CHROME_PX)
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
                if self.js.dispatch_event("click", elt): return
                unresolved_url = elt.attributes["href"]
                if unresolved_url not in visited_urls: visited_urls[unresolved_url] = True
                url = resolve_url(unresolved_url, self.url)
                if load:
                    return self.load(url)
                else:
                    return url
            elif elt.tag == "input":
                if self.js.dispatch_event("click", elt): return
                self.focus = elt
                if elt.attributes.get("type", "") == "checkbox":
                    elt.attributes["checked"] = True if "checked" not in elt.attributes else not bool(elt.attributes["checked"])
                else:
                    elt.attributes["value"] = ""
                self.render()
            elif elt.tag == "button":
                if self.js.dispatch_event("click", elt): return
                while elt:
                    if elt.tag == "form" and "action" in elt.attributes:
                        return self.submit_form(elt)
                    elt = elt.parent
            elt = elt.parent
    
    def submit_form_by_enter(self):
        if not self.focus:
            return
        elt = self.focus
        while elt:
            if elt.tag == "form" and "action" in elt.attributes:
                return self.submit_form(elt)
            elt = elt.parent

    def submit_form(self, elt):
        if self.js.dispatch_event("submit", elt): return
        inputs = [node for node in tree_to_list(elt, []) if isinstance(node, Element)
                  and node.tag == "input" and "name" in node.attributes]
        body = ""
        for input in inputs:
            name = urllib.parse.quote(input.attributes["name"])
            is_checkbox = input.attributes.get("type", "") == "checkbox"
            if is_checkbox:
                if bool(input.attributes.get("checked", False)):
                    value = urllib.parse.quote(input.attributes.get("value", "")) if "value" in input.attributes else "on"
                else:
                    continue
            else:
                value = urllib.parse.quote(input.attributes.get("value", ""))
            body += "&" + name + "=" + value
        body = body[1:]
        url = resolve_url(elt.attributes["action"], self.url)
        if "method" in elt.attributes and elt.attributes["method"].upper() == "GET":
            url += "?" + body
            self.load(url)
        else:
            self.load(url, req_body=body)
    
    def keypress(self, char):
        if self.focus:
            if self.focus.tag == "input" and self.focus.attributes.get("type", "") != "checkbox":
                if self.js.dispatch_event("keydown", self.focus): return
                self.focus.attributes["value"] += char
                self.render()
    
    def scroll_to_fragment(self, url):
        fragment = url.split("#")[1] if "#" in url else None
        if not fragment:
            return
        elements_with_id = [obj for obj in tree_to_list(self.document, [])
                   if isinstance(obj.node, Element) and obj.node.attributes.get("id", "") == fragment]
        if len(elements_with_id) < 1:
            return
        element = elements_with_id[-1]
        max_y = self.document.height - (self.browser.height - CHROME_PX)
        self.scroll = min(element.y, max_y)
    
    def blur(self):
        self.focus = None
    
    def switch_to_next_input(self):
        if self.focus and self.focus.tag == "input":
            input_elements = [obj.node for obj in tree_to_list(self.document, []) if isinstance(obj.node, Element)
                              and obj.node.tag == "input"]
            self.focus = input_elements[(input_elements.index(self.focus) + 1) % len(input_elements)]
            self.focus.attributes["value"] = ""
            self.render()

    def draw(self, canvas):
        for cmd in self.display_list:
            if cmd.top > self.scroll + self.browser.height - CHROME_PX: continue
            if cmd.bottom < self.scroll: continue
            cmd.execute(self.scroll - CHROME_PX, canvas)
        if self.focus:
            focus_objects = [obj for obj in tree_to_list(self.document, []) if obj.node == self.focus
                    and isinstance(obj, InputLayout)]
            if focus_objects:
                obj = focus_objects[0]
                type = self.focus.attributes.get("type", "")
                if type != "checkbox":
                    text = self.focus.attributes.get("value", "")
                    x = obj.x + obj.font.measure(text)
                    y = obj.y - self.scroll + CHROME_PX
                    canvas.create_line(x, y, x, y + obj.height, fill="black")
        self.drawScrollbar(canvas)
    
    def drawScrollbar(self, canvas):
        page_height = self.browser.height - CHROME_PX
        show_scrollbar = self.document.height > page_height
        if not show_scrollbar:
            return
        scrollbar_height = (page_height / self.document.height) * page_height
        scrollbar_offset = (self.scroll / self.document.height) * page_height + CHROME_PX
        canvas.create_rectangle(
            self.browser.width - 8, scrollbar_offset,
            self.browser.width, scrollbar_offset + scrollbar_height,
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
        self.text_cursor_position = 0
        self.bookmarks = set()
        self.window.bind("<Down>", self.handle_down)
        self.window.bind("<Up>", self.handle_up)
        self.window.bind("<MouseWheel>", self.handle_mousewheel)
        self.window.bind("<Configure>", self.handle_resize)
        self.window.bind("<Button-1>", self.handle_click)
        self.window.bind("<Button-2>", self.handle_middle_click)
        self.window.bind("<Key>", self.handle_key)
        self.window.bind("<Return>", self.handle_enter)
        self.window.bind("<BackSpace>", self.handle_backspace)
        self.window.bind("<Left>", self.handle_left)
        self.window.bind("<Right>", self.handle_right)
        self.window.bind("<Tab>", self.handle_tab)

    def handle_tab(self, e):
        self.tabs[self.active_tab].switch_to_next_input()
        self.draw()
    
    def draw(self):
        self.canvas.delete("all")
        # draw page content
        self.tabs[self.active_tab].draw(self.canvas)
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
        self.canvas.create_rectangle(70, 50, self.width - 60, 90, outline="black", width=1)
        if self.focus == "address bar":
            self.canvas.create_text(85, 55, anchor="nw", text=self.address_bar, font=buttonfont, fill="black")
            w = buttonfont.measure(self.address_bar[:self.text_cursor_position])
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
        # bookmark button
        bookmarkfont = get_font(12, "normal", "roman")
        bookmark_bgcolor = "yellow" if self.tabs[self.active_tab].url in self.bookmarks else None
        self.canvas.create_rectangle(self.width - 50, 50, self.width - 10, 90, outline="black", width=1, fill=bookmark_bgcolor)
        self.canvas.create_text(self.width - 44, 55, anchor="nw", text="book", font=bookmarkfont, fill="black")
        self.canvas.create_text(self.width - 44, 70, anchor="nw", text="mark", font=bookmarkfont, fill="black")

    def handle_down(self, e):
        self.tabs[self.active_tab].scrolldown()
        self.draw()
    
    def handle_up(self, e):
        self.tabs[self.active_tab].scrollup()
        self.draw()
    
    def handle_left(self, e):
        if self.focus == "address bar":
            self.text_cursor_position = max(0, self.text_cursor_position - 1)
            self.draw()
    
    def handle_right(self, e):
        if self.focus == "address bar":
            self.text_cursor_position = min(len(self.address_bar), self.text_cursor_position + 1)
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
            self.focus = None
            self.tabs[self.active_tab].blur()
            if 40 <= e.x < 40 + 80 * len(self.tabs) and 0 <= e.y < 40:
                self.active_tab = int((e.x - 40) / 80)
            elif 10 <= e.x < 30 and 10 <= e.y < 30:
                self.load("https://browser.engineering/")
            elif 10 <= e.x < 35 and 50 <= e.y < 90:
                self.tabs[self.active_tab].go_back()
            elif 40 <= e.x < 65 and 50 <= e.y < 90:
                self.tabs[self.active_tab].go_forward()
            elif 80 <= e.x < self.width - 60 and 40 <= e.y < 90:
                self.focus = "address bar"
                self.address_bar = ""
            elif self.width - 50 <= e.x < self.width - 10 and 50 <= e.y < 90:
                self.bookmark()
        else:
            self.focus = "content"
            self.tabs[self.active_tab].click(e.x, e.y - CHROME_PX)
        self.draw()
    
    def handle_middle_click(self, e):
        if e.y >= CHROME_PX:
            url = self.tabs[self.active_tab].click(e.x, e.y - CHROME_PX, load=False)
            if not url:
                return
            new_tab = Tab(self)
            new_tab.load(url)
            self.active_tab = len(self.tabs)
            self.tabs.append(new_tab)
            self.draw()
    
    def handle_key(self, e):
        if len(e.char) == 0: return
        if not (0x20 <= ord(e.char) < 0x7f): return

        if self.focus == "address bar":
            prefix = self.address_bar[:self.text_cursor_position]
            suffix = self.address_bar[self.text_cursor_position:]
            self.address_bar = prefix + e.char + suffix
            self.text_cursor_position += 1
            self.draw()
        elif self.focus == "content":
            self.tabs[self.active_tab].keypress(e.char)
            self.draw()
            
    
    def handle_enter(self, e):
        if self.focus == "address bar":
            self.tabs[self.active_tab].load(self.address_bar)
            self.focus = None
            self.draw()
        if self.focus == "content":
            self.tabs[self.active_tab].submit_form_by_enter()
            self.focus = None
            self.draw()
    
    def handle_backspace(self, e):
        if self.focus == "address bar":
            prefix = self.address_bar[:self.text_cursor_position]
            suffix = self.address_bar[self.text_cursor_position:]
            self.address_bar = prefix[:-1] + suffix
            self.text_cursor_position = max(self.text_cursor_position - 1, 0)
            self.draw()
    
    def bookmark(self):
        url = self.tabs[self.active_tab].url
        if url in self.bookmarks:
            self.bookmarks.remove(url)
        else:
            self.bookmarks.add(url)
        self.draw()
    
    def load(self, url):
        new_tab = Tab(self)
        new_tab.load(url)
        self.active_tab = len(self.tabs)
        self.tabs.append(new_tab)
        self.address_bar = ""
        self.focus = None
        self.draw()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) >= 2 else "file://test.html"
    Browser().load(url)
    tkinter.mainloop()

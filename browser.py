import sys
from helpers import resolve_url, tree_to_list, url_origin
from layout.inline_layout import get_font, visited_urls, InputLayout
from request import request
from parser import HTMLParser, ViewSourceParser, print_tree, Element, Text
from layout.document_layout import DocumentLayout
from constants import CHROME_PX, SCROLL_STEP, HEIGHT, WIDTH
from style import CSSParser, style, cascade_priority
import urllib.parse
import dukpy
from js_context import JSContext
import ctypes
import sdl2
import skia
from layout.skia_helpers import draw_rect, draw_line, draw_text, parse_color
import math

def handle_special_pages(url, browser):
    if url == "about:bookmarks":
        body = "<html><body><h1>Bookmarks</h1>"
        for bookmark in browser.bookmarks:
            body += "<a href=\"{}\"><li>{}</li>".format(bookmark, bookmark)
        body += "</body></html>"
        return None, body, False
    return None, None, False


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
        self.document = None
        self.is_secure_connection = False
        self.referrer_policy = None
    
    def load(self, url, back_or_forward=False, req_body=None, send_referrer=True):
        only_fragment_changed = self.url != None and self.url.split("#")[0] == url.split("#")[0] and req_body == None
        self.history.append((url, req_body))
        if only_fragment_changed:
            self.scroll_to_fragment(url)
        else:
            headers, body, view_source = handle_special_pages(url, self.browser)
            if not body:
                headers, body, view_source = request(url, self.url, payload=req_body, 
                    referrer_policy=self.referrer_policy, send_referrer=send_referrer)
            if view_source:
                self.nodes = ViewSourceParser(body).parse()
            else:
                self.nodes = HTMLParser(body).parse()
            self.is_secure_connection = "https" in url and not body.startswith("SSL Error:")
            # print_tree(self.nodes)
            self.referrer_policy = headers["referrer-policy"] if "referrer-policy" in headers else None
            self.allowed_origins = None
            if "content-security-policy" in headers:
                csp = headers["content-security-policy"].split()
                if len(csp) > 0 and csp[0] == "default-src":
                    self.allowed_origins = csp[1:]
            scripts = [node.attributes["src"] for node in tree_to_list(self.nodes, [])
                       if isinstance(node, Element) and node.tag == "script"
                       and "src" in node.attributes]
            self.js = JSContext(self)
            for script in scripts:
                script_url = resolve_url(script, url)
                if not self.allowed_request(script_url):
                    print("Blocked script", script, "due to CSP")
                    continue
                header, body, _ = request(script_url, url, referrer_policy=self.referrer_policy)
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
                    link_url = resolve_url(link, url)
                    if not self.allowed_request(link_url):
                        print("Blocked link", link_url, "due to CSP")
                        continue
                    header, body, _ = request(link_url, url, referrer_policy=self.referrer_policy)
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
        self.url = url
    
    def render(self):
        style(self.nodes, sorted(self.rules, key=cascade_priority))
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        self.document.paint(self.display_list)
    
    def go_back(self):
        if len(self.history) > 1:
            _, last_body = self.history[-2]
            if last_body:
                confirmed = self.confirm_form_resubmission()
                if not confirmed:
                    return
            forward = self.history.pop()
            self.future.append(forward)
            back_url, back_body = self.history.pop()
            self.load(back_url, back_or_forward=True, req_body=back_body, send_referrer=False)

    def go_forward(self):
        if len(self.future) > 0:
            _, next_body = self.future[-1]
            if next_body:
                confirmed = self.confirm_form_resubmission()
                if not confirmed:
                    return
            next_url, next_body = self.future.pop()
            self.load(next_url, back_or_forward=True, req_body=next_body, send_referrer=False)

    def confirm_form_resubmission(self):
        # return askyesno(title="Confirm form resubmission", message="Re-submitting post data, do you want to continue?")
        return True
    
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
            else:
                do_default, stop_propagation = self.js.dispatch_event("click", elt)
                if do_default:
                    if elt.tag == "a" and "href" in elt.attributes:
                        unresolved_url = elt.attributes["href"]
                        if unresolved_url not in visited_urls: visited_urls[unresolved_url] = True
                        url = resolve_url(unresolved_url, self.url)
                        if load:
                            self.load(url)
                        else:
                            return url
                    elif elt.tag == "input":
                        self.focus = elt
                        if elt.attributes.get("type", "") == "checkbox":
                            elt.attributes["checked"] = True if "checked" not in elt.attributes else not bool(elt.attributes["checked"])
                        else:
                            elt.attributes["value"] = ""
                        self.render()
                    elif elt.tag == "button":
                        elt_form = elt
                        while elt_form:
                            if elt_form.tag == "form" and "action" in elt_form.attributes:
                                return self.submit_form(elt_form)
                            elt_form = elt_form.parent
                if stop_propagation:
                    return
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
        do_default, _ = self.js.dispatch_event("submit", elt)
        if not do_default: return
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
                do_default, _ = self.js.dispatch_event("keydown", self.focus)
                if not do_default: return
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
            cmd.execute(canvas)
        if self.focus:
            focus_objects = [obj for obj in tree_to_list(self.document, []) if obj.node == self.focus
                    and isinstance(obj, InputLayout)]
            if focus_objects:
                obj = focus_objects[0]
                type = self.focus.attributes.get("type", "")
                if type != "checkbox":
                    text = self.focus.attributes.get("value", "")
                    x = obj.x + obj.font.measureText(text)
                    y = obj.y - self.scroll + CHROME_PX
                    # self.display_list.append(DrawLine(x, y, x, y + obj.height))
                    draw_line(canvas, x, y, x, y + obj.height)
    
    def resize(self, width):
        self.document.layout(width)
        self.display_list = []
        self.document.paint(self.display_list)
    
    def allowed_request(self, url):
        return self.allowed_origins == None or url_origin(url) in self.allowed_origins

class Browser:
    def __init__(self):
        self.chrome_surface = skia.Surface(WIDTH, CHROME_PX)
        self.tab_surface = None
        self.sdl_window = sdl2.SDL_CreateWindow(b"Browser",
            sdl2.SDL_WINDOWPOS_CENTERED, sdl2.SDL_WINDOWPOS_CENTERED,
            WIDTH, HEIGHT, sdl2.SDL_WINDOW_SHOWN)
        self.root_surface = skia.Surface.MakeRaster(
            skia.ImageInfo.Make(
                WIDTH, HEIGHT,
                ct=skia.kRGBA_8888_ColorType,
                at=skia.kUnpremul_AlphaType
            ))
        if sdl2.SDL_BYTEORDER == sdl2.SDL_BIG_ENDIAN:
            self.RED_MASK = 0xff000000
            self.GREEN_MASK = 0x00ff0000
            self.BLUE_MASK = 0x0000ff00
            self.ALPHA_MASK = 0x000000ff
        else:
            self.RED_MASK = 0x000000ff
            self.GREEN_MASK = 0x0000ff00
            self.BLUE_MASK = 0x00ff0000
            self.ALPHA_MASK = 0xff000000
        self.width = WIDTH
        self.height = HEIGHT
        # self.canvas.pack(expand=True, fill=tkinter.BOTH)
        self.zoom_factor = 1
        self.tabs = []
        self.active_tab = None
        self.focus = None
        self.address_bar = ""
        self.text_cursor_position = 0
        self.bookmarks = set()
        # self.window.bind("<Down>", self.handle_down)
        # self.window.bind("<Up>", self.handle_up)
        # self.window.bind("<MouseWheel>", self.handle_mousewheel)
        # self.window.bind("<Configure>", self.handle_resize)
        # self.window.bind("<Button-1>", self.handle_click)
        # self.window.bind("<Button-2>", self.handle_middle_click)
        # self.window.bind("<Key>", self.handle_key)
        # self.window.bind("<Return>", self.handle_enter)
        # self.window.bind("<BackSpace>", self.handle_backspace)
        # self.window.bind("<Left>", self.handle_left)
        # self.window.bind("<Right>", self.handle_right)
        # self.window.bind("<Tab>", self.handle_tab)

    def handle_tab(self, e):
        self.tabs[self.active_tab].switch_to_next_input()
        self.raster_tab()
        self.draw()
    
    def raster_tab(self):
        active_tab = self.tabs[self.active_tab]
        tab_height = math.ceil(active_tab.document.height)

        if not self.tab_surface or tab_height != self.tab_surface.height():
            self.tab_surface = skia.Surface(WIDTH, tab_height)
        canvas = self.tab_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)
        # draw page content
        self.tabs[self.active_tab].draw(canvas)
    
    def raster_chrome(self):
        canvas = self.chrome_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)
        # draw tabs
        draw_rect(canvas, -1, 0, WIDTH, CHROME_PX, fill="white")
        draw_rect(canvas, -1, 0, WIDTH, CHROME_PX - 1)
        tabfont = skia.Font(skia.Typeface('Arial'), 20)
        for i, tab in enumerate(self.tabs):
            name = "Tab {}".format(i)
            x1, x2 = 40 + 80 * i, 120 + 80 * i
            draw_line(canvas, x1, 0, x1, 40)
            draw_line(canvas, x2, 0, x2, 40)
            draw_text(canvas, x1 + 10, 10, name, tabfont)
            if i == self.active_tab:
                draw_line(canvas, 0, 40, x1, 40)
                draw_line(canvas, x2, 40, WIDTH, 40)
            buttonfont = skia.Font(skia.Typeface('Arial'), 30)
            draw_rect(canvas, 10, 10, 30, 30)
            draw_text(canvas, 11, 4, "+", buttonfont)
        # draw address bar
        draw_rect(canvas, 70, 50, WIDTH - 60, 90)
        if self.focus == "address bar":
            draw_text(canvas, 85, 55, self.address_bar, buttonfont)
            w = buttonfont.measureText(self.address_bar[:self.text_cursor_position])
            draw_line(canvas, 85 + w, 55, 85 + w, 85)
        else:
            url = self.tabs[self.active_tab].url
            draw_text(canvas, 85, 55, url, font=buttonfont)
            # if self.tabs[self.active_tab].is_secure_connection:
            #     draw_text(canvas, WIDTH - 80, 70, "HTTPS", buttonfont)
        # draw back button
        back_color = "black" if len(self.tabs[self.active_tab].history) > 1 else "gray"
        draw_rect(canvas, 10, 50, 35, 90)
        path = skia.Path().moveTo(15, 70).lineTo(30, 55).lineTo(30, 85)
        paint = skia.Paint(Color=parse_color(back_color), Style=skia.Paint.kFill_Style)
        canvas.drawPath(path, paint)
        # draw forward button
        forward_color = "black" if len(self.tabs[self.active_tab].future) > 0 else "gray"
        draw_rect(canvas, 40, 50, 65, 90)
        path = skia.Path().moveTo(45, 55).lineTo(60, 70).lineTo(45, 85)
        paint = skia.Paint(Color=parse_color(forward_color), Style=skia.Paint.kFill_Style)
        canvas.drawPath(path, paint)
        # bookmark button
        bookmarkfont = skia.Font(skia.Typeface('Arial'), 12)
        bookmark_bgcolor = "yellow" if self.tabs[self.active_tab].url in self.bookmarks else "white"
        draw_rect(canvas, WIDTH - 50, 50, WIDTH - 10, 90)
        draw_rect(canvas, WIDTH - 49, 51, WIDTH - 11, 89, fill=bookmark_bgcolor, width=10)
        draw_text(canvas, WIDTH - 44, 55, "book", bookmarkfont)
        draw_text(canvas, WIDTH - 44, 70, "mark", bookmarkfont)
    
    def draw(self):
        canvas = self.root_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)

        # draw tab
        tab_rect = skia.Rect.MakeLTRB(0, CHROME_PX, WIDTH, HEIGHT)
        tab_offset = CHROME_PX - self.tabs[self.active_tab].scroll
        canvas.save()
        canvas.clipRect(tab_rect)
        canvas.translate(0, tab_offset)
        self.tab_surface.draw(canvas, 0, 0)
        canvas.restore()

        # draw chrome
        chrome_rect = skia.Rect.MakeLTRB(0, 0, WIDTH, CHROME_PX)
        canvas.save()
        canvas.clipRect(chrome_rect)
        self.chrome_surface.draw(canvas, 0, 0)
        canvas.restore()

        skia_image = self.root_surface.makeImageSnapshot()
        skia_bytes = skia_image.tobytes()
        depth = 32
        pitch = 4 * WIDTH
        sdl_surface = sdl2.SDL_CreateRGBSurfaceFrom(
            skia_bytes, WIDTH, HEIGHT, depth, pitch, self.RED_MASK, 
            self.GREEN_MASK, self.BLUE_MASK, self.ALPHA_MASK)
        rect = sdl2.SDL_Rect(0, 0, WIDTH, HEIGHT)
        window_surface = sdl2.SDL_GetWindowSurface(self.sdl_window)
        sdl2.SDL_BlitSurface(sdl_surface, rect, window_surface, rect)
        sdl2.SDL_UpdateWindowSurface(self.sdl_window)

    def handle_down(self):
        self.tabs[self.active_tab].scrolldown()
        self.draw()
    
    def handle_up(self):
        self.tabs[self.active_tab].scrollup()
        self.draw()
    
    def handle_left(self, e):
        if self.focus == "address bar":
            self.text_cursor_position = max(0, self.text_cursor_position - 1)
            self.raster_chrome()
            self.draw()
    
    def handle_right(self, e):
        if self.focus == "address bar":
            self.text_cursor_position = min(len(self.address_bar), self.text_cursor_position + 1)
            self.raster_chrome()
            self.draw()
    
    def handle_mousewheel(self, e):
        # only works on mac due to how tk handles mouse wheel events
        if e.delta == 1:
            self.handle_up(e)
        elif e.delta == -1:
            self.handle_down()
    
    def handle_resize(self, e):
        if e.width > 1 and e.height > 1:
            self.width = e.width
            self.height = e.height
        self.tabs[self.active_tab].resize(self.width)
        self.raster_chrome()
        self.raster_tab
        self.draw()
    
    def handle_click(self, e):
        if e.y < CHROME_PX:
            self.focus = None
            self.tabs[self.active_tab].blur()
            if 40 <= e.x < 40 + 80 * len(self.tabs) and 0 <= e.y < 40:
                self.active_tab = int((e.x - 40) / 80)
                self.raster_tab()
            elif 10 <= e.x < 30 and 10 <= e.y < 30:
                self.load("https://browser.engineering/")
                self.raster_tab()
            elif 10 <= e.x < 35 and 50 <= e.y < 90:
                self.tabs[self.active_tab].go_back()
                self.raster_tab()
            elif 40 <= e.x < 65 and 50 <= e.y < 90:
                self.tabs[self.active_tab].go_forward()
                self.raster_tab()
            elif 80 <= e.x < self.width - 60 and 40 <= e.y < 90:
                self.focus = "address bar"
                self.address_bar = ""
            elif self.width - 50 <= e.x < self.width - 10 and 50 <= e.y < 90:
                self.bookmark()
            self.raster_chrome()
        else:
            self.focus = "content"
            self.tabs[self.active_tab].click(e.x, e.y - CHROME_PX)
            self.raster_tab()
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
            self.raster_chrome()
            self.raster_tab()
            self.draw()
    
    def handle_key(self, char):
        if len(char) == 0: return
        if not (0x20 <= ord(char) < 0x7f): return

        if self.focus == "address bar":
            prefix = self.address_bar[:self.text_cursor_position]
            suffix = self.address_bar[self.text_cursor_position:]
            self.address_bar = prefix + char + suffix
            self.text_cursor_position += 1
            self.raster_chrome()
            self.draw()
        elif self.focus == "content":
            self.tabs[self.active_tab].keypress(char)
            self.raster_tab()
            self.draw()
    
    def handle_enter(self):
        if self.focus == "address bar":
            self.tabs[self.active_tab].load(self.address_bar, send_referrer=False)
            self.focus = None
            self.raster_chrome()
            self.raster_tab()
            self.draw()
        if self.focus == "content":
            self.tabs[self.active_tab].submit_form_by_enter()
            self.focus = None
            self.raster_tab()
            self.draw()
    
    def handle_backspace(self):
        if self.focus == "address bar":
            prefix = self.address_bar[:self.text_cursor_position]
            suffix = self.address_bar[self.text_cursor_position:]
            self.address_bar = prefix[:-1] + suffix
            self.text_cursor_position = max(self.text_cursor_position - 1, 0)
            self.raster_chrome()
            self.draw()
    
    def bookmark(self):
        url = self.tabs[self.active_tab].url
        if url in self.bookmarks:
            self.bookmarks.remove(url)
        else:
            self.bookmarks.add(url)
        self.raster_chrome()    
        self.draw()
    
    def load(self, url):
        new_tab = Tab(self)
        new_tab.load(url, send_referrer=False)
        self.active_tab = len(self.tabs)
        self.tabs.append(new_tab)
        self.address_bar = ""
        self.focus = None
        self.raster_chrome()
        self.raster_tab()
        self.draw()
    
    def handle_quit(self):
        sdl2.SDL_DestroyWindow(self.sdl_window)

if __name__ == "__main__":
    import sys
    sdl2.SDL_Init(sdl2.SDL_INIT_EVENTS)
    browser = Browser()
    url = sys.argv[1] if len(sys.argv) >= 2 else "file://test.html"
    browser.load(url)
    event = sdl2.SDL_Event()
    while True:
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_QUIT:
                browser.handle_quit()
                sdl2.SDL_Quit()
                sys.exit()
            elif event.type == sdl2.SDL_MOUSEBUTTONUP:
                browser.handle_click(event.button)
            elif event.type == sdl2.SDL_KEYDOWN:
                if event.key.keysym.sym == sdl2.SDLK_RETURN:
                    browser.handle_enter()
                elif event.key.keysym.sym == sdl2.SDLK_DOWN:
                    browser.handle_down()
                elif event.key.keysym.sym == sdl2.SDLK_UP:
                    browser.handle_up()
                elif event.key.keysym.sym == sdl2.SDLK_BACKSPACE:
                    browser.handle_backspace()
            elif event.type == sdl2.SDL_TEXTINPUT:
                browser.handle_key(event.text.text.decode('utf8'))

import sys
from helpers import resolve_url, tree_to_list, url_origin
from layout.inline_layout import get_font, visited_urls, InputLayout
from request import request
from parser import HTMLParser, ViewSourceParser, print_tree, Element, Text
from layout.document_layout import DocumentLayout
from constants import CHROME_PX, SCROLL_STEP, HEIGHT, WIDTH, INTEREST_REGION_SIZE, REFRESH_RATE_SEC
from style import CSSParser, style, cascade_priority
import urllib.parse
import dukpy
from js_context import JSContext
import ctypes
import sdl2
import skia
from layout.skia_helpers import draw_rect, draw_line, draw_text, parse_color
import layout.skia_helpers
import ctypes
from layout.drawing import scrolldown_element, scrollup_element
from taskrunner import TaskRunner, Task
import threading
import time

def handle_special_pages(url, browser):
    if url == "about:bookmarks":
        body = "<html><body><h1>Bookmarks</h1>"
        for bookmark in browser.bookmarks:
            body += "<a href=\"{}\"><li>{}</li>".format(bookmark, bookmark)
        body += "</body></html>"
        return None, body, False
    return None, None, False

class CommitForRaster:
    def __init__(self, url, scroll, height, display_list, interest_region):
        self.url = url
        self.scroll = scroll
        self.height = height
        self.display_list = display_list
        self.interest_region = interest_region

class MeasureTime:
    def __init__(self, name):
        self.name = name
        self.start_time = None
        self.total_s = 0
        self.count = 0

    def text(self):
        if self.count == 0: return ""
        avg = self.total_s / self.count
        return "Time in {} on average: {:>.0f}ms".format(self.name, avg * 1000)
    
    def start(self):
        self.start_time = time.time()
    
    def stop(self):
        self.total_s += time.time() - self.start_time
        self.count += 1
        self.start_time = None

class Tab:
    def __init__(self, browser):
        with open("browser.css") as f:
            self.default_style_sheet = CSSParser(f.read()).parse()
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
        self.interest_region = [0, 0]
        self.task_runner = TaskRunner()
        self.task_runner.start()
        self.needs_render = False
        self.measure_render = MeasureTime("render")
        self.scroll = 0
        self.scroll_changed_in_tab = False
    
    def run_script(self, url, body):
        try:
            print("Script returned: ", self.js.run(body))
        except dukpy.JSRuntimeError as e:
            print("Script", url, "crashed", e)

    def load(self, url, back_or_forward=False, req_body=None, send_referrer=True):
        only_fragment_changed = self.url != None and self.url.split("#")[0] == url.split("#")[0] and req_body == None
        self.history.append((url, req_body))
        if not back_or_forward:
            self.future = []
        if only_fragment_changed:
            self.url = url
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
                task = Task(self.run_script, script_url, body)
                self.task_runner.schedule_task(task)
                # try:
                #     self.js.run(body)
                # except dukpy.JSRuntimeError as e:
                #     print("Script", script, "crashed", e)
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
            self.set_needs_render()
            self.scroll = 0
            self.scroll_changed_in_tab = True
            self.url = url
            self.scroll_to_fragment(url)
    
    def render(self):
        if not self.needs_render:
            # print("[tab] render (skipping)", self.url)
            return
        print("[tab] render ", self.url)
        self.measure_render.start()
        self.needs_render = False
        style(self.nodes, sorted(self.rules, key=cascade_priority))
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        self.document.paint(self.display_list)
        self.measure_render.stop()
        if self.interest_region == [0, 0]:
            self.compute_interest_region(self.scroll)
    
    def run_animation_frame(self, scroll):
        # print("[tab] run_animation_frame")
        if not self.scroll_changed_in_tab:
            self.scroll = scroll
        # print("run_animation_frame scroll:", scroll, " self.scroll:", self.scroll)
        self.js.interp.evaljs("__runRAFHandlers()")
        self.render()
        document_height = self.document.height
        clamped_scroll = clamp_scroll(self.scroll, document_height)
        if clamped_scroll != self.scroll:
            self.scroll_changed_in_tab = True
        self.scroll = clamped_scroll

        scroll = None
        if self.scroll_changed_in_tab:
            scroll = self.scroll
        commit_data = CommitForRaster(
            url=self.url,
            scroll=scroll,
            height=document_height,
            display_list=self.display_list,
            interest_region=self.interest_region,
        )
        # print("run_animation_frame - commiting interest_region", self.interest_region)
        self.display_list = None
        self.browser.commit(self, commit_data)
        self.scroll_changed_in_tab = False
    
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

    def click(self, x, y, load = True):
        self.render() # needed?
        def hittest(obj, x, y):
            within_bounds = obj.x <= x < obj.x + obj.width and obj.y <= y < obj.y + obj.height
            if not within_bounds:
                return False
            radius = float(obj.node.style.get("border-radius", "0px")[:-2])
            if radius == 0:
                return within_bounds
            else:
                rect = skia.Rect.MakeLTRB(obj.x, obj.y, obj.x + obj.width, obj.y + obj.height)
                rrect = skia.RRect.MakeRectXY(rect, radius, radius)
                click_location = skia.Rect.MakeLTRB(x, y, x + 1, y + 1)
                return rrect.contains(click_location)
        set_scroll_focus = False
        # print("[tab] click self.scroll: ", self.scroll)
        y += self.scroll
        objs = [obj for obj in tree_to_list(self.document, []) if hittest(obj, x, y)]
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
                        self.set_needs_render()
                    elif elt.tag == "button":
                        elt_form = elt
                        while elt_form:
                            if elt_form.tag == "form" and "action" in elt_form.attributes:
                                return self.submit_form(elt_form)
                            elt_form = elt_form.parent
                    elif elt.style.get("overflow", "") == "scroll" and not set_scroll_focus:
                        self.focus = elt
                        set_scroll_focus = True
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
                self.set_needs_render()

    def scroll_to_fragment(self, url):
        # print("scroll to fragment")
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
        self.compute_interest_region(self.scroll)
        self.scroll_changed_in_tab = True
        self.set_needs_render()
    
    def blur(self):
        self.focus = None
    
    def switch_to_next_input(self):
        if self.focus and self.focus.tag == "input":
            input_elements = [obj.node for obj in tree_to_list(self.document, []) if isinstance(obj.node, Element)
                              and obj.node.tag == "input"]
            self.focus = input_elements[(input_elements.index(self.focus) + 1) % len(input_elements)]
            self.focus.attributes["value"] = ""
            self.set_needs_render()
    
    def compute_interest_region(self, scroll):
        # interest region is in dots, not pixels
        new_scroll = 0
        absolute_scroll = self.interest_region[0] + scroll
        new_region_start = absolute_scroll - INTEREST_REGION_SIZE / 2
        extra_space_top, extra_space_bottom = 0, 0
        if new_region_start < 0:
            extra_space_top = -new_region_start
        new_region_end = absolute_scroll + INTEREST_REGION_SIZE / 2
        if new_region_end > self.document.height:
            extra_space_bottom = new_region_end - self.document.height;
        new_region_start = max(0, new_region_start - extra_space_bottom)
        new_region_end = min(self.document.height, new_region_end + extra_space_top)
        self.interest_region = [new_region_start, new_region_end]
        new_scroll = absolute_scroll - self.interest_region[0]
        # print("computed interest region: ", self.interest_region, " new_scroll: ", new_scroll)
        self.scroll = new_scroll
        self.scroll_changed_in_tab = True
        self.browser.set_needs_animation_frame(self)
    
    def draw_input_focus(self, canvas):
        focus_objects = [obj for obj in tree_to_list(self.document, []) if obj.node == self.focus
                and isinstance(obj, InputLayout)]
        if focus_objects:
            obj = focus_objects[0]
            type = self.focus.attributes.get("type", "")
            if type != "checkbox":
                text = self.focus.attributes.get("value", "")
                x = obj.x + obj.font.measureText(text)
                y = obj.y
                # self.display_list.append(DrawLine(x, y, x, y + obj.height))
                draw_line(canvas, x, y, x, y + obj.height, width=2)
    
    def resize(self, width):
        self.document.layout(width)
        self.display_list = []
        self.document.paint(self.display_list)
    
    def allowed_request(self, url):
        return self.allowed_origins == None or url_origin(url) in self.allowed_origins
    
    def set_needs_render(self):
        self.needs_render = True
        self.browser.set_needs_animation_frame(self)
    
    def handle_quit(self):
        print(self.measure_render.text())
    
    def set_scroll(self, scroll):
        self.scroll = scroll
        self.scroll_changed_in_tab = True

def raster(canvas, display_list, interest_region, scale):
    # if not self.document: return
    canvas.save()
    canvas.clipRect(skia.Rect.MakeLTRB(0, 0, WIDTH * scale, INTEREST_REGION_SIZE * browser.scale))
    # print("raster - translation: ", -interest_region[0] * scale)
    # print("interest region", interest_region)
    canvas.translate(0, -interest_region[0] * scale)
    for cmd in display_list:
        cmd.execute(canvas)
    # if self.focus:
    #     self.draw_input_focus(canvas)
    canvas.restore()

def clamp_scroll(scroll, tab_height):
    return max(0, min(scroll, tab_height - (HEIGHT - CHROME_PX)))

class Browser:
    def __init__(self):
        self.sdl_window = sdl2.SDL_CreateWindow(b"Browser",
            sdl2.SDL_WINDOWPOS_CENTERED, sdl2.SDL_WINDOWPOS_CENTERED,
            WIDTH, HEIGHT, sdl2.SDL_WINDOW_SHOWN | sdl2.SDL_WINDOW_ALLOW_HIGHDPI)
        w, h = ctypes.c_int(), ctypes.c_int()
        self.renderer = sdl2.SDL_CreateRenderer(self.sdl_window, -1, 0)
        # print(self.renderer)
        sdl2.SDL_GetRendererOutputSize(self.renderer, w, h)
        # print("Renderer output size: {} {}".format(w, h))
        # wr, hr = ctypes.c_float(), ctypes.c_float()
        self.scale = int(w.value / WIDTH)
        layout.skia_helpers.scale_factor = self.scale
        # print("scale: {}".format(scale))
        # print(sdl2.SDL_RenderSetScale(self.renderer, 30, 30))
        # sdl2.SDL_RenderGetScale(self.renderer, wr, hr)
        # print("Renderer Scale: {} {}".format(wr, hr))
        # res = sdl2.SDL_RenderSetScale(self.renderer, 2, 2)
        # if res < 0:
        #     # out = ctypes.c_char_p
            # print(sdl2.SDL_GetError())
        self.root_surface = skia.Surface.MakeRaster(
            skia.ImageInfo.Make(
                self.scale * WIDTH, self.scale * HEIGHT,
                ct=skia.kRGBA_8888_ColorType,
                at=skia.kUnpremul_AlphaType
            ))
        self.chrome_surface = skia.Surface(self.scale * WIDTH, self.scale * CHROME_PX)
        self.tab_surface = None
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
        self.zoom_factor = 1
        self.tabs = []
        self.active_tab = None
        self.focus = None
        self.address_bar = ""
        self.text_cursor_position = 0
        self.bookmarks = set()
        self.needs_raster_and_draw = False
        self.animation_timer = None
        self.needs_animation_frame = True
        self.measure_raster_and_draw = MeasureTime("raster-and-draw")
        self.lock = threading.Lock()
        self.url = None
        self.scroll = 0
        self.active_tab_height = 0
        self.active_tab_display_list = None
        self.active_tab_interest_region = None
    
    def set_active_tab(self, index):
        if self.active_tab != None:
            active_tab = self.tabs[self.active_tab]
            set_scroll_task = Task(active_tab.set_scroll, self.scroll)
            active_tab.task_runner.schedule_task(set_scroll_task)
        self.active_tab = index
        self.scroll = 0
        self.url = None
        self.active_tab_display_list = []
        self.needs_animation_frame = True
    
    def commit(self, tab, data):
        self.lock.acquire(blocking=True)
        if tab == self.tabs[self.active_tab]:
            self.url = data.url
            if data.scroll != None:
                self.scroll = data.scroll
            self.active_tab_height = data.height
            if data.display_list:
                self.active_tab_display_list = data.display_list
            self.animation_timer = None
            self.active_tab_interest_region = data.interest_region
            # print("commit -> raster and draw")
            self.set_needs_raster_and_draw()
        self.lock.release()

    def set_needs_raster_and_draw(self):
        self.needs_raster_and_draw = True
        self.needs_animation_frame = True
    
    def set_needs_animation_frame(self, tab):
        self.lock.acquire(blocking=True)
        if tab == self.tabs[self.active_tab]:
            self.needs_animation_frame = True
        self.lock.release()

    def handle_tab(self, e):
        self.lock.acquire(blocking=True)
        active_tab = self.tabs[self.active_tab]
        task = Task(active_tab.switch_to_next_input)
        active_tab.task_runner.schedule_task(task)
        self.lock.release()
    
    def raster_tab(self):
        if not self.tab_surface:
            self.tab_surface = skia.Surface(self.scale * WIDTH, self.scale * INTEREST_REGION_SIZE)
        canvas = self.tab_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)
        # draw page content
        raster(
            canvas, 
            self.active_tab_display_list, 
            self.active_tab_interest_region,
            self.scale
        )
        # self.tabs[self.active_tab].draw(canvas)
    
    def raster_chrome(self):
        # print("raster chrome")
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
            draw_line(canvas, 85 + w, 55, 85 + w, 85, width=2)
        else:
            if self.url:
                draw_text(canvas, 85, 55, self.url, font=buttonfont)
        # draw back button
        back_color = "black" if len(self.tabs[self.active_tab].history) > 1 else "gray"
        draw_rect(canvas, 10, 50, 35, 90)
        path = skia.Path().moveTo(self.scale * 15, self.scale * 70).lineTo(self.scale * 30, self.scale * 55).lineTo(self.scale * 30, self.scale * 85)
        paint = skia.Paint(Color=parse_color(back_color), Style=skia.Paint.kFill_Style)
        canvas.drawPath(path, paint)
        # draw forward button
        forward_color = "black" if len(self.tabs[self.active_tab].future) > 0 else "gray"
        draw_rect(canvas, 40, 50, 65, 90)
        path = skia.Path().moveTo(self.scale * 45, self.scale * 55).lineTo(self.scale * 60, self.scale * 70).lineTo(self.scale * 45, self.scale * 85)
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
        tab_rect = skia.Rect.MakeLTRB(0, self.scale * CHROME_PX, self.scale * WIDTH, self.scale * HEIGHT)
        tab_offset = self.scale * (CHROME_PX - self.scroll)
        # print("drawing offset with scroll: ", self.scroll)
        canvas.save()
        canvas.clipRect(tab_rect)
        canvas.translate(0, tab_offset)
        self.tab_surface.draw(canvas, 0, 0)
        canvas.restore()

        # draw chrome
        chrome_rect = skia.Rect.MakeLTRB(0, 0, self.scale * WIDTH, self.scale * CHROME_PX)
        canvas.save()
        canvas.clipRect(chrome_rect)
        self.chrome_surface.draw(canvas, 0, 0)
        canvas.restore()

        skia_image = self.root_surface.makeImageSnapshot()
        # skia_image = skia_image.resize(WIDTH, HEIGHT, filterQuality=skia.FilterQuality.kHigh_FilterQuality)
        skia_bytes = skia_image.tobytes()
        depth = 32
        pitch = 4 * self.scale * WIDTH
        sdl_surface = sdl2.SDL_CreateRGBSurfaceFrom(
            skia_bytes, self.scale * WIDTH, self.scale * HEIGHT, depth, pitch, self.RED_MASK, 
            self.GREEN_MASK, self.BLUE_MASK, self.ALPHA_MASK)
        # scaled = sdl2.sdlgfx.zoomSurface(sdl_surface, 0.5, 0.5, 1)
        # rect = sdl2.SDL_Rect(0, 0, WIDTH, HEIGHT)
        # dest_rect = sdl2.SDL_Rect(0, 0, WIDTH, HEIGHT)
        # window_surface = sdl2.SDL_GetWindowSurface(self.sdl_window)
        # sdl2.SDL_BlitSurface(sdl_surface, rect, window_surface, rect)
        texture = sdl2.SDL_CreateTextureFromSurface(self.renderer, sdl_surface)
        sdl2.SDL_RenderClear(self.renderer)
        sdl2.SDL_RenderCopy(self.renderer, texture, None, None)
        sdl2.SDL_RenderPresent(self.renderer)
        # sdl2.SDL_UpdateWindowSurface(self.sdl_window)
    
    def scrolldown(self):
        max_y = max(0, self.active_tab_height - (self.height - CHROME_PX))
        
        absolute_scroll = self.active_tab_interest_region[0] + self.scroll
        new_absolute_scroll = min(absolute_scroll + SCROLL_STEP, max_y)

        new_scroll = new_absolute_scroll - self.active_tab_interest_region[0]
        # compute new region if we moved close towards end of current region
        if new_scroll != self.scroll and new_absolute_scroll + (self.height - CHROME_PX) + SCROLL_STEP >= self.active_tab_interest_region[1]:
            active_tab = self.tabs[self.active_tab]
            active_tab.task_runner.schedule_task(Task(active_tab.compute_interest_region, new_scroll))
        return new_scroll

    def scrollup(self):
        absolute_scroll = self.active_tab_interest_region[0] + self.scroll
        new_absolute_scroll = max(0, absolute_scroll - SCROLL_STEP)

        new_scroll = new_absolute_scroll - self.active_tab_interest_region[0]
        # compute new region if we moved closed towards start of current region
        if new_scroll != self.scroll and new_scroll <= SCROLL_STEP:
            active_tab = self.tabs[self.active_tab]
            active_tab.task_runner.schedule_task(Task(active_tab.compute_interest_region, new_scroll))
        return new_scroll

    def handle_down(self):
        self.lock.acquire(blocking=True)
        if not self.active_tab_height:
            self.lock.release()
            return
        scroll = self.scrolldown()
        self.scroll = scroll
        self.set_needs_raster_and_draw()
        self.lock.release()
    
    def handle_up(self):
        self.lock.acquire(blocking=True)
        if not self.active_tab_height:
            self.lock.release()
            return
        scroll = self.scrollup()
        self.scroll = scroll
        self.set_needs_raster_and_draw()
        self.lock.release()
    
    def handle_left(self, e):
        self.lock.acquire(blocking=True)
        if self.focus == "address bar":
            self.text_cursor_position = max(0, self.text_cursor_position - 1)
            self.set_needs_raster_and_draw()
        self.lock.release()
    
    def handle_right(self, e):
        self.lock.acquire(blocking=True)
        if self.focus == "address bar":
            self.text_cursor_position = min(len(self.address_bar), self.text_cursor_position + 1)
            self.set_needs_raster_and_draw()
        self.lock.release()
    
    def handle_click(self, e):
        self.lock.acquire(blocking=True)
        if e.y < CHROME_PX:
            self.focus = None
            active_tab = self.tabs[self.active_tab]
            task = Task(active_tab.blur)
            active_tab.task_runner.schedule_task(task)
            if 40 <= e.x < 40 + 80 * len(self.tabs) and 0 <= e.y < 40:
                self.set_active_tab(int((e.x - 40) / 80))
                active_tab = self.tabs[self.active_tab]
                task = Task(active_tab.set_needs_render)
                active_tab.task_runner.schedule_task(task)
            elif 10 <= e.x < 30 and 10 <= e.y < 30:
                self.load_internal("https://browser.engineering/")
            elif 10 <= e.x < 35 and 50 <= e.y < 90:
                task = Task(active_tab.go_back)
                active_tab.task_runner.schedule_task(task)
            elif 40 <= e.x < 65 and 50 <= e.y < 90:
                task = Task(active_tab.go_forward)
                active_tab.task_runner.schedule_task(task)
            elif 80 <= e.x < self.width - 60 and 40 <= e.y < 90:
                self.focus = "address bar"
                self.address_bar = ""
            elif self.width - 50 <= e.x < self.width - 10 and 50 <= e.y < 90:
                self.bookmark()
            self.set_needs_raster_and_draw()
        else:
            self.focus = "content"
            active_tab = self.tabs[self.active_tab]
            # print("[browser] handle_click self.scroll: ", self.scroll)
            task = Task(active_tab.click, e.x, e.y - CHROME_PX)
            active_tab.task_runner.schedule_task(task)
        self.lock.release()
    
    def handle_key(self, char):
        if len(char) == 0: return
        if not (0x20 <= ord(char) < 0x7f): return
        self.lock.acquire(blocking=True)
        if self.focus == "address bar":
            prefix = self.address_bar[:self.text_cursor_position]
            suffix = self.address_bar[self.text_cursor_position:]
            self.address_bar = prefix + char + suffix
            self.text_cursor_position += 1
            self.set_needs_raster_and_draw()
        elif self.focus == "content":
            active_tab = self.tabs[active_tab]
            task = Task(active_tab.keypress, char)
            active_tab.task_runner.schedule_task(task)
        self.lock.release()
    
    def handle_enter(self):
        self.lock.acquire(blocking=True)
        if self.focus == "address bar":
            self.schedule_load(self.address_bar)
            self.focus = None
            self.set_needs_raster_and_draw()
        if self.focus == "content":
            active_tab = self.tabs[self.active_tab]
            task = Task(active_tab.submit_form_by_enter)
            active_tab.task_runner.schedule_task(task)
            self.focus = None
            self.set_needs_raster_and_draw()
        self.lock.release()
    
    def handle_backspace(self):
        self.lock.acquire(blocking=True)
        if self.focus == "address bar":
            prefix = self.address_bar[:self.text_cursor_position]
            suffix = self.address_bar[self.text_cursor_position:]
            self.address_bar = prefix[:-1] + suffix
            self.text_cursor_position = max(self.text_cursor_position - 1, 0)
            self.set_needs_raster_and_draw()
        self.lock.release()
    
    def bookmark(self):
        url = self.tabs[self.active_tab].url
        if url in self.bookmarks:
            self.bookmarks.remove(url)
        else:
            self.bookmarks.add(url)
        self.set_needs_raster_and_draw()
    
    def schedule_load(self, url, body=None, send_referrer=False):
        active_tab = self.tabs[self.active_tab]
        task = Task(active_tab.load, url, body, send_referrer)
        active_tab.task_runner.schedule_task(task)
    
    def load(self, url):
        self.lock.acquire(blocking=True)
        self.load_internal(url)
        self.lock.release()
        # self.schedule_animation_frame()
        # self.set_needs_raster_and_draw()
    
    def load_internal(self, url):
        new_tab = Tab(self)
        self.set_active_tab(len(self.tabs))
        self.tabs.append(new_tab)
        self.schedule_load(url)
        self.address_bar = ""
        self.focus = None
    
    def raster_and_draw(self):
        self.lock.acquire(blocking=True)
        if not self.needs_raster_and_draw:
            self.lock.release()
            return
        # print("[browser] raster_and_draw")
        self.measure_raster_and_draw.start()
        self.raster_chrome()
        self.raster_tab()
        self.draw()
        self.needs_raster_and_draw = False
        self.measure_raster_and_draw.stop()
        self.lock.release()
    
    def handle_quit(self):
        # self.tabs[self.active_tab].handle_quit()
        print(self.measure_raster_and_draw.text())
        sdl2.SDL_DestroyWindow(self.sdl_window)
    
    def schedule_animation_frame(self):
        def callback():
            self.lock.acquire(blocking=True)
            scroll = self.scroll
            active_tab = self.tabs[self.active_tab]
            self.needs_animation_frame = False
            task = Task(active_tab.run_animation_frame, scroll)
            active_tab.task_runner.schedule_task(task)
            self.animation_timer = None
            self.lock.release()
        self.lock.acquire(blocking=True)
        if self.needs_animation_frame and not self.animation_timer:
            self.animation_timer = threading.Timer(REFRESH_RATE_SEC, callback)
            self.animation_timer.start()
        self.lock.release()

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
        # browser.tabs[browser.active_tab].task_runner.run()
        browser.raster_and_draw()
        browser.schedule_animation_frame()

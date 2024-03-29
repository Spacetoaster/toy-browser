import skia
import layout.skia_helpers
from .skia_helpers import draw_line, draw_text, draw_rect, draw_rrect, scale_rrect
from transform_parser import TransformParser

class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.top = y1
        self.left = x1
        self.right = x1 + font.measureText(text)
        self.text = text
        self.font = font
        lineheight = font.getMetrics().fDescent - font.getMetrics().fAscent
        self.bottom = y1 + lineheight
        self.color = color
        self.rect = skia.Rect.MakeLTRB(x1, y1, self.right, self.bottom)
    
    def execute(self, canvas):
        draw_text(
            canvas, 
            self.left, 
            self.top, 
            self.text, 
            self.font, 
            self.color
        )


class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color
        self.rect = skia.Rect.MakeLTRB(x1, y1, x2, y2)
    
    def execute(self, canvas):
        draw_rect(
            canvas,
            self.left,
            self.top,
            self.right,
            self.bottom,
            fill=self.color,
            width=0
        )

class DrawRRect:
    def __init__(self, rect, radius, color):
        self.rect = rect
        self.top = self.rect.top()
        self.left = self.rect.left()
        self.right = self.rect.right()
        self.bottom = self.rect.bottom()
        self.rrect = skia.RRect.MakeRectXY(rect, radius, radius)
        self.radius = radius
        self.color = color
        self.radius = radius
    
    def execute(self, canvas):
        draw_rrect(canvas, self.rrect, self.radius, self.color)

class DrawLine:
    def __init__(self, x1, y1, x2, y2):
        self.rect = skia.Rect.MakeLTRB(x1, y1, x2, y2)
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
    
    def execute(self, canvas):
        draw_line(canvas, self.x1, self.x1, self.x2, self.y2)

class DrawCheckmark:
    def __init__(self, x1, y1, x2, y2):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2

    def execute(self, canvas):
        draw_line(canvas,
            self.left + 1, self.top + 1,
            self.right - 1, self.bottom - 1, width=2)
        draw_line(canvas,
            self.left + 1, self.bottom - 1,
            self.right - 1, self.top + 1, width=2)

class SaveLayer:
    def __init__(self, sk_paint, children, should_save=True, should_paint_cmds=True, blur=0, z_index=0):
        self.sk_paint = sk_paint
        self.children = children
        self.should_save = should_save
        self.should_paint_cmds = should_paint_cmds
        self.rect = skia.Rect.MakeEmpty()
        for cmd in self.children:
            self.rect.join(cmd.rect)
        self.blur = blur
        self.z_index = z_index
    
    def execute(self, canvas):
        if self.should_save:
            if self.blur != 0:
                scaled_blur = layout.skia_helpers.scale_factor * self.blur
                self.sk_paint.setImageFilter(skia.BlurImageFilter.Make(scaled_blur, scaled_blur))
            canvas.saveLayer(paint=self.sk_paint)
        if self.should_paint_cmds:
            for cmd in self.children:
                cmd.execute(canvas)
        if self.should_save:
            canvas.restore()

def reorder_by_z_index(cmds):
    def order(cmd):
        if not isinstance(cmd, SaveLayer):
            return 0
        return cmd.z_index
    return sorted(cmds, key=order)

class ClipRRect:
    def __init__(self, rect, radius, children, should_clip=True, scroll=0, has_background=False):
        self.rect = rect
        self.rrect = skia.RRect.MakeRectXY(rect, radius, radius)
        self.children = children
        self.should_clip = should_clip
        self.radius = radius
        self.scroll = scroll
        self.has_background = has_background
    
    def execute(self, canvas):
        if self.should_clip:
            canvas.save()
            canvas.clipRRect(scale_rrect(self.rrect, self.radius))
        
        sorted_cmds = reorder_by_z_index(self.children)
        if self.has_background:
            sorted_cmds[0].execute(canvas)
            sorted_cmds = sorted_cmds[1:]
        if self.scroll:
            canvas.translate(0, -self.scroll)
        for cmd in sorted_cmds:
            cmd.execute(canvas)
        
        if self.should_clip:
            canvas.restore()

class Transform:
    def __init__(self, rect, transform, children):
        self.rect = rect
        self.children = children
        self.transform_cmds = TransformParser(transform).parse()

    def execute(self, canvas):
        should_transform = len(self.transform_cmds) > 0
        if should_transform:
            canvas.save()
            for transform_cmd in self.transform_cmds:
                if transform_cmd[0] == "rotate":
                    center_x = self.rect.left() + 0.5 * (self.rect.right() - self.rect.left())
                    center_y = self.rect.top() + 0.5 * (self.rect.bottom() - self.rect.top())
                    scaled_center_x = center_x * layout.skia_helpers.scale_factor
                    scaled_center_y = center_y * layout.skia_helpers.scale_factor
                    canvas.rotate(transform_cmd[1], scaled_center_x, scaled_center_y)
                elif transform_cmd[0] == "translate":
                    x, y = transform_cmd[1]
                    scaled_x = x * layout.skia_helpers.scale_factor
                    scaled_y = y * layout.skia_helpers.scale_factor
                    canvas.translate(scaled_x, scaled_y)

        for cmd in self.children:
            cmd.execute(canvas)

        if should_transform:
            canvas.restore()

def paint_visual_effects(node, cmds, rect):
    opacity = float(node.style.get("opacity", "1.0"))
    blend_mode = parse_blend_mode(node.style.get("mix-blend-mode"))
    border_radius = float(node.style.get("border-radius", "0px")[:-2])
    overflow = node.style.get("overflow", "visible")
    if overflow in ["clip", "scroll"]:
        clip_radius = border_radius
    else:
        clip_radius = 0
    needs_clip = overflow in ["clip", "scroll"]
    needs_blend_isolation = blend_mode != skia.BlendMode.kSrcOver or needs_clip
    needs_opacity = opacity != 1.0
    transform = node.style.get("transform", "")
    blur = parse_blur_filter(node.style.get("filter"))
    z_index = int(node.style.get("z-index", "0")) if node.style.get("position", "static") != "static" else 0

    needs_scroll = node.style.get("overflow", "") == "scroll"
    if needs_scroll and not node in SCROLL_STATES:
        inner_rect = skia.Rect.MakeEmpty()
        for cmd in cmds:
            inner_rect.join(cmd.rect)
        print(rect)
        print(inner_rect)
        SCROLL_STATES[node] = (0, rect.height(), inner_rect.height())
    scroll = SCROLL_STATES[node][0] if needs_scroll else 0
    has_background = node.style.get("background-color", "") != ""

    return [
        SaveLayer(skia.Paint(BlendMode=blend_mode, Alphaf=opacity), [
            Transform(rect, transform, [
                ClipRRect(rect, clip_radius, cmds, should_clip=needs_clip, scroll=scroll, has_background=has_background)
            ])
        ], should_save=needs_blend_isolation or needs_opacity or blur, blur=blur, z_index=z_index)
    ]

def parse_blend_mode(blend_mode_str):
    if blend_mode_str == "multiply":
        return skia.BlendMode.kMultiply
    elif blend_mode_str == "difference":
        return skia.BlendMode.kDifference
    else:
        return skia.BlendMode.kSrcOver

# only works with single filter and without whitespaces
def parse_blur_filter(filter_str):
    if not filter_str:
        return 0
    filter_str = filter_str.strip().split()[0]
    if not filter_str.startswith("blur("):
        return 0
    filter_str = filter_str[5:]
    if filter_str.endswith(");"):
        filter_str = filter_str[:-2]
    elif filter_str.endswith(")"):
        filter_str = filter_str[:-1]
    if filter_str.endswith("px"):
        filter_str = filter_str[:-2]
    filter_str = filter_str.strip()
    if not filter_str.isnumeric():
        return 0
    return int(filter_str)

SCROLL_STATES = {}

def scrolldown_element(node):
    if not SCROLL_STATES[node]:
        return
    scroll, height, inner_height = SCROLL_STATES[node]
    max_scroll = max(0, layout.skia_helpers.scale_factor * (inner_height - height))
    new_scroll = min(scroll + 20, max_scroll)
    SCROLL_STATES[node] = (new_scroll, height, inner_height)


def scrollup_element(node):
    if not SCROLL_STATES[node]:
        return
    scroll, height, inner_height = SCROLL_STATES[node]
    new_scroll = max(scroll - 20, 0)
    SCROLL_STATES[node] = (new_scroll, height, inner_height)
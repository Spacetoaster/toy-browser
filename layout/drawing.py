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
            self.left + 2, self.top + 2,
            self.right - 3, self.bottom - 3)
        draw_line(canvas,
            self.left + 2, self.bottom - 3,
            self.right - 3, self.top + 2)

class SaveLayer:
    def __init__(self, sk_paint, children, should_save=True, should_paint_cmds=True):
        self.sk_paint = sk_paint
        self.children = children
        self.should_save = should_save
        self.should_paint_cmds = should_paint_cmds
        self.rect = skia.Rect.MakeEmpty()
        for cmd in self.children:
            self.rect.join(cmd.rect)
    
    def execute(self, canvas):
        if self.should_save:
            canvas.saveLayer(paint=self.sk_paint)
        if self.should_paint_cmds:
            for cmd in self.children:
                cmd.execute(canvas)
        if self.should_save:
            canvas.restore()

class ClipRRect:
    def __init__(self, rect, radius, children, should_clip=True):
        self.rect = rect
        self.rrect = skia.RRect.MakeRectXY(rect, radius, radius)
        self.children = children
        self.should_clip = should_clip
        self.radius = radius
    
    def execute(self, canvas):
        if self.should_clip:
            canvas.save()
            canvas.clipRRect(scale_rrect(self.rrect, self.radius))
        
        for cmd in self.children:
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
    if node.style.get("overflow", "visible") == "clip":
        clip_radius = border_radius
    else:
        clip_radius = 0
    needs_clip = node.style.get("overflow", "visible") == "clip"
    needs_blend_isolation = blend_mode != skia.BlendMode.kSrcOver or needs_clip
    needs_opacity = opacity != 1.0
    transform = node.style.get("transform", "")

    return [
        SaveLayer(skia.Paint(BlendMode=blend_mode, Alphaf=opacity), [
            Transform(rect, transform, [
                ClipRRect(rect, clip_radius, cmds, should_clip=needs_clip)
            ])
        ], should_save=needs_blend_isolation or needs_opacity) # what about needs_opacity?
    ]

def parse_blend_mode(blend_mode_str):
    if blend_mode_str == "multiply":
        return skia.BlendMode.kMultiply
    elif blend_mode_str == "difference":
        return skia.BlendMode.kDifference
    else:
        return skia.BlendMode.kSrcOver
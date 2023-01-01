from parser import Text, Element
from .inline_layout import InlineLayout
from .canvas_layout import CanvasLayout
from .drawing import DrawRRect, paint_visual_effects
import skia

def layout_mode(node):
    if isinstance(node, Text):
        return "inline"
    elif node.children:
        for child in node.children:
            if isinstance(child, Text): continue
            if child.style.get("display", "inline") == "block":
                return "block"
        return "inline"
    elif node.tag == "input":
        return "inline"
    else:
        return "block"

class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def compute_width(self):
        css_width = self.node.style.get('width', 'auto')
        if css_width == 'auto':
            self.width = self.parent.width
        elif css_width.endswith('%'):
            self.width = int(self.parent.width * float(css_width[:-1]) / 100)
        elif css_width.endswith('px'):
            self.width = int(css_width[:-2])
    
    def compute_height(self):
        css_height = self.node.style.get('height', 'auto')
        if css_height == 'auto':
            self.height = sum([child.height for child in self.children])
        elif css_height.endswith('px'):
            self.height = int(css_height[:-2])
    
    def layout(self):
        self.compute_width()
        self.x = self.parent.x
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        previous = None
        for child in self.node.children:
            if isinstance(child, Element) and child.tag == "head": continue
            if isinstance(child, Element) and child.tag == "canvas": next = CanvasLayout(child, self, previous)
            elif layout_mode(child) == "inline":
                next = InlineLayout(child, self, previous)
            else:
                next = BlockLayout(child, self, previous)
            self.children.append(next)
            previous = next
        for child in self.children:
            child.layout()
        self.compute_height()
    
    def paint(self, display_list):
        cmds = []
        bgcolor = self.node.style.get("background-color", "transparent")
        rect = skia.Rect.MakeLTRB(self.x, self.y, self.x + self.width, self.y + self.height)
        if bgcolor != "transparent":
            radius = float(self.node.style.get("border-radius", "0px")[:-2])
            cmds.append(DrawRRect(rect, radius, bgcolor))
        for child in self.children:
            child.paint(cmds)
        cmds = paint_visual_effects(self.node, cmds, rect)
        display_list.extend(cmds)

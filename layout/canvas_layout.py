from copy import copy
from .drawing import DrawRect, DrawText

canvasContexts = {}

def add_draw_cmd(node, draw_cmd):
    if not node in canvasContexts:
        canvasContexts[node] = []
    canvasContexts[node].append(draw_cmd)

class CanvasLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self):
        self.x = self.parent.x
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        self.width = 300
        self.height = 150

    def paint(self, display_list):
        display_list.append(DrawRect(self.x, self.y, self.x + self.width, self.y + self.height, "lightgrey"))
        context = canvasContexts.get(self.node)
        if not context:
            return
        for draw_cmd in context:
            draw_cmd_copy = copy(draw_cmd)
            if isinstance(draw_cmd_copy, DrawRect):
                draw_cmd_copy.top += self.y
                draw_cmd_copy.left += self.x
                draw_cmd_copy.bottom += self.y
                draw_cmd_copy.right += self.x
            elif isinstance(draw_cmd_copy, DrawText):
                draw_cmd_copy.top += self.y
                draw_cmd_copy.bottom += self.y
                draw_cmd_copy.left += self.x
            display_list.append(draw_cmd_copy)

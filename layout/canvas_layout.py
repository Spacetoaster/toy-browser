from .drawing import DrawRect, DrawText

canvasContexts = {}

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
    
    def add_draw_cmd(self, draw_cmd):
        if not self.node in canvasContexts:
            canvasContexts[self.node] = []
        if isinstance(DrawRect, draw_cmd):
            draw_cmd.top += self.y
            draw_cmd.left += self.x
            draw_cmd.bottom += self.y
            draw_cmd.right += self.x
        elif isinstance(DrawText, draw_cmd):
            draw_cmd.top += self.y
            draw_cmd.bottom += self.y
            draw_cmd.left += self.x
        canvasContexts[self.node].append(draw_cmd)
    
    def paint(self, display_list):
        # display_list.append(DrawRect(self.x, self.y, self.x + self.width, self.y + self.height, "lightgrey"))
        context = canvasContexts.get(self.node)
        if not context:
            return
        for draw_cmd in context:
            display_list.append(draw_cmd)

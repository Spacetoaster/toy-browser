from constants import WIDTH, HSTEP, VSTEP
from .block_layout import BlockLayout

class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = node
        self.children = []
    
    def layout(self, width = WIDTH):
        self.children = []
        self.width = width - 2 * HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child = BlockLayout(self.node, self, None)
        self.children.append(child)
        child.layout()
        self.height = child.height + 2 * VSTEP
    
    def paint(self, display_list):
        self.children[0].paint(display_list)
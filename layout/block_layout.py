from parser import Text, Element
from .inline_layout import InlineLayout

def layout_mode(node):
    if isinstance(node, Text):
        return "inline"
    elif node.children:
        for child in node.children:
            if isinstance(child, Text): continue
            if child.style.get("display", "inline") == "block":
                return "block"
        return "inline"
    else:
        return "block"

def is_run_in_heading_edgecase(inline_layout_sequence_nodes, child):
    return (len(inline_layout_sequence_nodes) == 1
        and isinstance(inline_layout_sequence_nodes[0], Element) 
        and inline_layout_sequence_nodes[0].tag == "h6" 
        and child.tag == "p" 
        and layout_mode(child) == "inline")

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
        inline_layout_sequence_nodes = []
        for child in self.node.children:
            if isinstance(child, Element) and child.tag == "head": continue
            if isinstance(child, Text) or child.style.get("display", "inline") == "inline":
                inline_layout_sequence_nodes.append(child)
                continue
            elif inline_layout_sequence_nodes:
                run_in_heading_edgecase = is_run_in_heading_edgecase(inline_layout_sequence_nodes, child)
                if run_in_heading_edgecase:
                    inline_layout_sequence_nodes.append(child)
                next = InlineLayout(inline_layout_sequence_nodes, self, previous)
                self.children.append(next)
                previous = next
                inline_layout_sequence_nodes = []
                if run_in_heading_edgecase:
                    continue
            if layout_mode(child) == "inline":
                next = InlineLayout([child], self, previous)
            else:
                next = BlockLayout(child, self, previous)
            self.children.append(next)
            previous = next
        if inline_layout_sequence_nodes:
            self.children.append(InlineLayout(inline_layout_sequence_nodes, self, previous))
        for child in self.children:
            child.layout()
        self.compute_height()
    
    def paint(self, display_list):
        for child in self.children:
            child.paint(display_list)
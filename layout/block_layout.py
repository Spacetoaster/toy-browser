from parser import Text, Element
from .inline_layout import InlineLayout

BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
]

def layout_mode(node):
    if isinstance(node, Text):
        return "inline"
    elif node.children:
        for child in node.children:
            if isinstance(child, Text): continue
            if child.tag in BLOCK_ELEMENTS:
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
        # chapter 5 exercise, maybe remove later
        if isinstance(self.node, Element) and self.node.tag == "nav":
            if 'id' in self.node.attributes and self.node.attributes['id'] == 'toc':
                node = Text("Table of Contents", self.node)
                if not isinstance(self.node.children[0], Text):
                    self.node.children.insert(0, node)
    
    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        previous = None
        inline_layout_sequence_nodes = []
        for child in self.node.children:
            if isinstance(child, Element) and child.tag == "head": continue
            if isinstance(child, Text) or child.tag not in BLOCK_ELEMENTS or child.tag == "h6":
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
        self.height = sum([child.height for child in self.children])
    
    def paint(self, display_list):
        for child in self.children:
            child.paint(display_list)
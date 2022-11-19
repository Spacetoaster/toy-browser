class Text:
    def __init__(self, text, parent):
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&shy;", "\N{soft hyphen}")
        self.text = text
        self.children = []
        self.parent = parent
    
    def __repr__(self):
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.children = []
        self.parent = parent
        self.attributes = attributes
    
    def __repr__(self):
        attributes = ""
        for key in self.attributes:
            attributes += key + "=" + self.attributes[key] + ";"
        out = "<" + self.tag + ">"
        if attributes:
            out += " (attributes: " + attributes + ")"
        return out

class HTMLParser:
    SELF_CLOSING_TAGS = [
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    ]
    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "style", "script",
    ]

    def __init__(self, body):
        self.body = body
        self.unfinished = []

    def parse(self):
        text = ""
        in_tag = False
        in_comment = False
        in_script = False
        in_double_quote_attribute = False
        in_single_quote_attribute = False
        for c in self.body:
            in_attribute = in_single_quote_attribute or in_double_quote_attribute
            if c == "<" and not in_comment and not in_attribute:
                in_tag = True
                if text and not in_script: self.add_text(text)
                text = ""
            elif c == ">" and not in_comment and not in_attribute:
                in_tag = False
                if text == "p" and "p" in [node.tag for node in self.unfinished]:
                    self.add_tag("/p")
                if text == "script":
                    in_script = True
                if not in_script: self.add_tag(text)
                elif text == "/script":
                    in_script = False
                text = ""
            else:
                text += c
                if in_tag and text == "!--":
                    in_comment = True
                if in_comment and text.endswith("-->"):
                    in_comment = False
                    in_tag = False
                    text = ""
                if in_tag:
                    if not in_double_quote_attribute and text.endswith("=\""):
                        in_double_quote_attribute = True
                    elif in_double_quote_attribute and text.endswith("\"") and not text.endswith("\\\""):
                        in_double_quote_attribute = False
                    if not in_single_quote_attribute and text.endswith("='"):
                        in_single_quote_attribute = True
                    elif in_single_quote_attribute and text.endswith("'") and not text.endswith("\\'"):
                        in_single_quote_attribute = False
        if not in_tag and text and not in_script:
            self.add_text(text)
        return self.finish()
    
    def add_text(self, text):
        if text.isspace(): return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)
    
    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        if tag.startswith("!"): return
        self.implicit_tags(tag)
        if tag.startswith("/"):
            if len(self.unfinished) == 1: return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)
    
    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ["html"] and tag not in ["head", "body", "/html"]:
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ["html", "head"] and tag not in ["/head"] + self.HEAD_TAGS:
                self.add_tag("/head")
            else:
                break
    
    def finish(self):
        if len(self.unfinished) == 0:
            self.add_tag("html")
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()
    
    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].lower()
        attributes = {}
        append_attribute_key = None
        quote_char = None
        for attrpair in parts[1:]:
            if append_attribute_key:
                value = attrpair
                if value.endswith(quote_char) and not value.endswith("\\{}".format(quote_char)):
                    value = value[:len(value) - 1]
                    attributes[append_attribute_key] += " " + value
                    quote_char = None
                    append_attribute_key = None
                else:
                    attributes[append_attribute_key] += " " + value
            elif "=" in attrpair:
                key, value = attrpair.split("=", 1)
                if len(value) >= 2 and value[0] in ["'", "\""]:
                    quote_char = value[0]
                    value = value[1:]
                if quote_char and value.endswith(quote_char) and not value.endswith("\\{}".format(quote_char)):
                    value = value[:len(value) - 1]
                    append_attribute_key = None
                else:
                    append_attribute_key = key.lower()
                attributes[key.lower()] = value
            else:
                attributes[attrpair.lower()] = ""
        return tag, attributes

class ViewSourceParser(HTMLParser):
    def __init__(self, body):
        super().__init__(body)
    
    def parse(self):
        text = ""
        in_tag = False
        for c in self.body:
            if c == "<":
                in_tag = True
                if text.strip():
                    self.add_tag("pre")
                    self.add_tag("b")
                    self.add_text(text)
                    self.add_tag("/b")
                    self.add_tag("/pre")
                text = ""
            elif c == ">":
                in_tag = False
                self.add_text("<{}>".format(text))
                text = ""
            else:
                text += c
        if not in_tag and text:
            self.add_text(text)
        return self.finish()
    
def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)    
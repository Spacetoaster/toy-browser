from layout.canvas_layout import add_draw_cmd
from layout.inline_layout import get_font
from layout.drawing import DrawRect, DrawText
from parser import HTMLParser, Element
from style import CSSParser
from helpers import tree_to_list, node_tree_to_html, resolve_url, url_origin
from request import request
import dukpy

EVENT_DISPATCH_CODE = "new Node(dukpy.handle).dispatchEvent(new Event(dukpy.type))"

class JSContext:
    def __init__(self, tab):
        self.tab = tab
        self.interp = dukpy.JSInterpreter()
        self.interp.export_function("log", print)
        self.interp.export_function("querySelectorAll", self.querySelectorAll)
        self.interp.export_function("getAttribute", self.getAttribute)
        self.interp.export_function("innerHTML_set", self.innerHTML_set)
        self.interp.export_function("innerHTML_get", self.innerHTML_get)
        self.interp.export_function("outerHTML_get", self.outerHTML_get)
        self.interp.export_function("children", self.children)
        self.interp.export_function("createElement", self.create_element)
        self.interp.export_function("appendChild", self.append_child)
        self.interp.export_function("insertBefore", self.insert_before)
        self.interp.export_function("removeChild", self.remove_child)
        self.interp.export_function("canvas.fillRect", self.fill_rect)
        self.interp.export_function("canvas.fillText", self.fill_text)
        self.interp.export_function("getStyle", self.get_style)
        self.interp.export_function("setStyle", self.set_style)
        self.interp.export_function("XMLHttpRequest_send", self.XMLHttpRequest_send)
        with open("runtime.js") as f:
            self.interp.evaljs(f.read())
        self.node_to_handle = {}
        self.handle_to_node = {}
        self.add_global_vars_for_tree(self.tab.nodes)

    def run(self, code):
        return self.interp.evaljs(code)
    
    def clear_global_vars_for_tree(self, node):
        nodes_with_id = [node for node in tree_to_list(node, [])
                    if isinstance(node, Element) and node.attributes.get("id", "") != ""]
        if "id" in node.attributes:
            nodes_with_id.append(node)
        for node in nodes_with_id:
            id = node.attributes.get("id")
            self.run("{} = undefined;".format(id))

    def add_global_vars_for_tree(self, node):
        nodes_with_id = [node for node in tree_to_list(node, [])
                          if isinstance(node, Element) and node.attributes.get("id", "") != ""]
        if "id" in node.attributes:
            nodes_with_id.append(node)
        for node in nodes_with_id:
            id = node.attributes.get("id")
            if not id or not id.isalpha():
                continue
            handle = self.get_handle(node)
            self.run("var {} = new Node({});".format(id, handle))

    def get_handle(self, elt):
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle)
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
        else:
            handle = self.node_to_handle[elt]
        return handle

    def querySelectorAll(self, selector_text):
        selector = CSSParser(selector_text).selector()
        nodes = [node for node in tree_to_list(self.tab.nodes, []) if selector.matches(node)]
        return [self.get_handle(node) for node in nodes]
    
    def getAttribute(self, handle, attr):
        elt = self.handle_to_node[handle]
        return elt.attributes.get(attr, None)
    
    def dispatch_event(self, type, elt):
        handle = self.node_to_handle.get(elt, -1)
        ret = self.interp.evaljs(EVENT_DISPATCH_CODE, type=type, handle=handle)
        return ret["do_default"], ret["stop_propagation"]

    def innerHTML_set(self, handle, s):
        doc = HTMLParser("<html><body>" + s + "</body></html>").parse()
        new_nodes = doc.children[0].children
        elt = self.handle_to_node[handle]
        elt.children = new_nodes
        for child in elt.children:
            child.parent = elt
            self.add_global_vars_for_tree(child)
        self.tab.render()
    
    def innerHTML_get(self, handle):
        elt = self.handle_to_node[handle]
        out = node_tree_to_html(elt, False)
        return out

    def outerHTML_get(self, handle):
        elt = self.handle_to_node[handle]
        out = node_tree_to_html(elt, True)
        return out

    def children(self, handle):
        elt = self.handle_to_node[handle]
        handles = [self.get_handle(child) for child in elt.children if isinstance(child, Element)]
        return handles

    def create_element(self, tagName):
        elt = Element(tagName, {}, None)
        return self.get_handle(elt)

    def append_child(self, handle, child_handle):
        if not handle in self.handle_to_node or not child_handle in self.handle_to_node:
            return
        node = self.handle_to_node[handle]
        child = self.handle_to_node[child_handle]
        node.children.append(child)
        child.parent = node
        self.add_global_vars_for_tree(node)
        self.tab.render()

    def insert_before(self, handle, new_node_handle, child_handle):
        assert handle in self.handle_to_node, "can't find matching parent for handle"
        assert new_node_handle in self.handle_to_node, "can't find matching new_node for handle"
        node = self.handle_to_node[handle]
        new_node = self.handle_to_node[new_node_handle]
        child_index = None
        deleted_node_index = None
        if child_handle:
            assert child_handle in self.handle_to_node, "can't find matching child for handle"
            child = self.handle_to_node[child_handle]
            assert child in node.children, "child node is not a child of parent"
            child_index = node.children.index(child)
        if new_node in node.children:
            deleted_node_index = node.children.index(new_node)
            node.children.remove(new_node)
        if child_index:
            if deleted_node_index and child_index >= deleted_node_index:
                child_index -= 1
            node.children.insert(child_index, new_node)
        else:
            node.children.append(new_node)
        new_node.parent = node
        self.add_global_vars_for_tree(new_node)
        self.tab.render()

    def remove_child(self, handle, child_handle):
        assert handle in self.handle_to_node, "can't find matching node for handle"
        assert child_handle in self.handle_to_node, "can't find matching node for child handle"
        parent = self.handle_to_node[handle]
        child = self.handle_to_node[child_handle]
        assert child in parent.children, "child node is not a child of parent"
        parent.children.remove(child)
        child.parent = None
        self.tab.render()
        self.clear_global_vars_for_tree(child)
        return child_handle
    
    def fill_rect(self, handle, x, y, w, h, fillStyle):
        canvas_element = self.handle_to_node[handle]
        if not (isinstance(canvas_element, Element) and canvas_element.tag == "canvas"):
            return
        add_draw_cmd(canvas_element, DrawRect(x, y, x + w, y + h, fillStyle))
        # only call render if document is already fully loaded
        if self.tab.document:
            self.tab.render()
    
    def fill_text(self, handle, text, x, y, fillStyle):
        canvas_element = self.handle_to_node[handle]
        if not (isinstance(canvas_element, Element) and canvas_element.tag == "canvas"):
            return
        font = get_font(10, "normal", "roman") 
        add_draw_cmd(canvas_element, DrawText(x, y, text, font, fillStyle))
        # only call render if document is already fully loaded
        if self.tab.document:
            self.tab.render()
    
    def get_style(self, handle):
        elt = self.handle_to_node[handle]
        if not isinstance(elt, Element): return
        style = elt.attributes.get("style")
        if not style:
            return {}
        rules = CSSParser(style).body()
        return rules
    
    def set_style(self, handle, attribute, value):
        elt = self.handle_to_node[handle]
        if not isinstance(elt, Element): return
        rules = self.get_style(handle)
        rules[attribute] = value
        cssText = ""
        for attr in rules:
            cssText += "{}: {};".format(attr, rules[attr])
        elt.attributes["style"] = cssText
        # only call render if document is already fully loaded
        if self.tab.document:
            self.tab.render()
    
    def XMLHttpRequest_send(self, method, url, body):
        full_url = resolve_url(url, self.tab.url)
        if not self.tab.allowed_request(full_url):
            raise Exception("Cross-origin XHR blocked by CSP")
        if url_origin(full_url) != url_origin(self.tab.url):
            raise Exception("Cross-origin XHR request not allowed")
        headers, out = request(full_url, self.tab.url, body)
        return out


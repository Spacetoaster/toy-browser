class TransformParser:
    def __init__(self, s):
        self.s = s
        self.i = 0

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def literal(self, literal):
        assert self.i < len(self.s) and self.s[self.i] == literal
        self.i += 1

    def word(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] == "-":
                self.i += 1
            else:
                break
        assert self.i > start
        return self.s[start:self.i].strip()

    def transform(self):
        start = self.i
        while self.i < len(self.s):
            c = self.s[self.i]
            if c in "rotate" or c in "translate":
                self.i += 1
            else:
                break
        return self.s[start:self.i]

    def rotate_val(self):
        self.literal("(")
        self.whitespace()
        val = self.word()
        self.whitespace()
        self.literal(")")
        assert "deg" in val
        val = val[:-3]
        return int(val)

    def translate_val(self):
        self.literal("(")
        self.whitespace()
        x = self.word()
        self.whitespace()
        self.literal(",")
        self.whitespace()
        y = self.word()
        self.whitespace()
        self.literal(")")
        if "px" in x: x = x[:-2]
        if "px" in y: y = y[:-2]
        return int(x), int(y)

    def parse(self):
        cmds = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                transform = self.transform()
                if transform == "rotate":
                    val = self.rotate_val()
                elif transform == "translate":
                    val = self.translate_val()
                cmds.append((transform, val))
                if self.i < len(self.s) and self.s[self.i] == ";":
                    break
            except AssertionError:
                cmds = []
                return cmds
        return cmds
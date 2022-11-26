class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.bottom = y1 + font.metrics("linespace")
        self.color = color
    
    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left, self.top - scroll,
            text=self.text,
            font=self.font,
            anchor='nw',
            fill=self.color
        )

class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color
    
    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.left, self.top - scroll,
            self.right, self.bottom - scroll,
            width=0,
            fill=self.color,
        )

class DrawCheckmark:
    def __init__(self, x1, y1, x2, y2):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2

    def execute(self, scroll, canvas):
        canvas.create_line(
            self.left + 2, self.top - scroll + 2,
            self.right - 3, self.bottom - scroll - 3,
            fill="black")
        canvas.create_line(
            self.left + 2, self.bottom - scroll - 3,
            self.right - 3, self.top - scroll + 2,
            fill="black")
function lengthCheck() {
  var name = this.getAttribute("name");
  var value = this.getAttribute("value");
  if (value.length > 5) {
    console.log("Input " + name + "has too much text.");
    var test = document.querySelectorAll(".innerHtmlTest")
    test[0].innerHTML = "this was set by JS!"
  }
}

var inputs = document.querySelectorAll("input");
for (var i = 0; i < inputs.length; i++) {
  inputs[i].addEventListener("keydown", lengthCheck)
}

buttonwithonclick.addEventListener("click", function(e) {
  e.preventDefault()
  console.log("button clicked");
  color = paragraph.style.backgroundColor
  paragraph.style.backgroundColor = color == "yellow" ? "white" : "yellow";
  paragraph.style.fontSize = color == "yellow" ? "100%" : "150%";
  console.log(paragraph.style.backgroundColor)
})

inner.addEventListener("click", function(e) {
  console.log("inner clicked")
  e.stopPropagation();
})

outer.addEventListener("click", function(e) {
  console.log("outer clicked")
})

fragmentlink.addEventListener("click", function(e) {
  console.log("scrolling")
})

context = canvasNode.getContext("2d");
context.fillRect(0, 0, 50, 50);
context.fillStyle = "yellow";
context.fillRect(50, 50, 25, 25);
context.fillStyle = "black";
context.fillText("Hello world", 60, 60)
context.fillText("Hello world", 65, 65)
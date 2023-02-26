function lengthCheck() {
  var name = this.getAttribute("name");
  var value = this.getAttribute("value");
  if (value.length > 5) {
    console.log("Input " + name + "has too much text.");
  }
}

var inputs = document.querySelectorAll("input");
for (var i = 0; i < inputs.length; i++) {
  inputs[i].addEventListener("keydown", lengthCheck)
}

buttonwithonclick.addEventListener("click", function(e) {
  e.preventDefault()
  // console.log("button clicked");
  // color = paragraph.style.backgroundColor
  // paragraph.style.backgroundColor = color == "yellow" ? "white" : "yellow";
  // paragraph.style.fontSize = color == "yellow" ? "100%" : "150%";

  paragraph.innerHTML = '<span id=foo>Chris was here</span>';
  paragraph.id = 'bar';
  // Prints "<span id=bar>Chris was here</span>":
  console.log(paragraph.innerHTML);
  console.log(paragraph.outerHTML);
  // console.log(paragraph.style.backgroundColor)
  // console.log(paragraph.innerHTML)
})

inner.addEventListener("click", function(e) {
  console.log("inner clicked")
  e.stopPropagation();
})

outer.addEventListener("click", function(e) {
  console.log("outer clicked")
})

fragmentlink.addEventListener("click", function(e) {
  console.log("start counter")
  // for (var i = 0; i < 5e7; i++);
  console.log("scrolling")
})

context = canvasNode.getContext("2d");
context.fillRect(0, 0, 50, 50);
context.fillStyle = "yellow";
context.fillRect(50, 50, 25, 25);
context.fillStyle = "black";
context.fillText("Hello world", 60, 60)
context.fillText("Hello world", 65, 65)

orangebox.addEventListener("click", function() {
  console.log("clicked")
})

// setTimeout(function() {
//   console.log("timer ran")
// }, 2000)
// setTimeout(function() {
//   console.log("timer ran")
// }, 4000)
// setTimeout(function() {
//   console.log("timer ran")
// }, 6000)
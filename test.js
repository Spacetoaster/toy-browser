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

var testButtons = document.querySelectorAll(".testButtons")[0].children
var blabla = document.querySelectorAll(".blabla")[0]

testButtons[0].addEventListener("click", function(e) {
  e.preventDefault()
  var test = document.querySelectorAll(".innerHtmlTest")
  var n = document.createElement("h1")
  n.innerHTML = "appended"
  test[0].appendChild(n)
})

testButtons[1].addEventListener("click", function(e) {
  e.preventDefault()
  var test = document.querySelectorAll(".innerHtmlTest")
  var num_children = test[0].children.length
  if (num_children < 1) {
    return
  }
  var new_node = document.createElement("h1")
  new_node.innerHTML = "inserted before"
  last_child = test[0].children[num_children - 1]
  test[0].insertBefore(blabla, last_child)
})

var b = null
testButtons[2].addEventListener("click", function(e) {
  e.preventDefault()
  var body = document.querySelectorAll("body")[0]
  var innerHtmlTest2 = document.querySelectorAll(".innerHtmlTest2")[0]
  b = body.removeChild(innerHtmlTest2)
  console.log(b.handle)
})

testButtons[3].addEventListener("click", function(e) {
  e.preventDefault()
  var test = document.querySelectorAll(".innerHtmlTest")
  var num_children = test[0].children.length
  if (num_children < 1) {
    return
  }
  last_child = test[0].children[num_children - 1]
  console.log(b.handle)
  test[0].insertBefore(b, last_child)
})

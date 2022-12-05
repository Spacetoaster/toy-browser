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

testButtons.children[0].addEventListener("click", function(e) {
  e.preventDefault()

  var node_with_id = document.createElement("div")
  node_with_id.innerHTML = "<div id='new_id'></div>"
  test.insertBefore(node_with_id, null)
  console.log(test)
  console.log(new_id)
})

testButtons.children[1].addEventListener("click", function(e) {
  e.preventDefault()

  test.children[test.children.length - 1].removeChild(new_id)
  console.log(test)
  console.log(new_id)
})


console.log(test)
console.log(new_id)
var ws = new WebSocket("ws://127.0.0.1:5455/");
var my_uid = "<removed>";
var my_name = "<removed>";

ws.onmessage = function(event) {
  document.querySelectorAll('.new_row').forEach(e => e.classList.remove("new_row"));
  document.getElementById("trades_tbody").insertAdjacentHTML("afterbegin", event.data);
};

function sendMessage(elem) {
  let prompt_msg = "Message to " + elem.dataset.uname;
  if (elem.dataset.uname !== elem.dataset.pname) {
    prompt_msg += " (" + elem.dataset.pname + ")";
  }
  let msg = prompt(prompt_msg);
  if (msg === null) {
    return;
  }
  elem.removeAttribute("onclick");
  elem.classList.remove("cursor_pointer");
  elem.classList.add("disabled");
  elem.classList.add("cursor_default");
  let s = '{"data":{"members":[{"uid":"' + my_uid + '","username":"' + my_name + '"},{"uid":"' + elem.dataset.uid + '","username":"' + elem.dataset.uname + '"}],"body":"' + msg + '"}}';
  ws.send(s);
}
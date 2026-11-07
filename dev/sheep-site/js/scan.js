(function () {
  var scan = document.getElementById("scan");
  var mask = document.getElementById("mask");
  var plate = document.getElementById("plate");
  var lens = document.getElementById("lens");
  var touchId = null;

  function metrics(touch) {
    var width = scan.getBoundingClientRect().width;
    var phone = touch || window.matchMedia("(max-width: 760px)").matches;
    if (phone) {
      return {
        radius: Math.max(78, Math.min(width * 0.27, 108)),
        zoom: 3.85
      };
    }
    return {
      radius: Math.max(90, Math.min(width * 0.32, 128)),
      zoom: 1.45
    };
  }

  function place(clientX, clientY, touch) {
    var rect = scan.getBoundingClientRect();
    var sampleX = clientX - rect.left;
    var sampleY = clientY - rect.top;
    var m = metrics(touch);
    var lift = 0;
    if (touch) {
      var wanted = Math.round(m.radius * 0.42 + 36);
      var viewY = sampleY - wanted;
      if (viewY < m.radius * 0.55) viewY = Math.min(sampleY, m.radius * 0.55);
      lift = sampleY - viewY;
    }
    var viewX = sampleX;
    var viewY = sampleY - lift;
    mask.style.clipPath = "circle(" + m.radius + "px at " + viewX + "px " + viewY + "px)";
    plate.style.transformOrigin = sampleX + "px " + sampleY + "px";
    plate.style.transform = "translate(0px, " + (-lift) + "px) scale(" + m.zoom + ")";
    lens.style.left = viewX + "px";
    lens.style.top = viewY + "px";
    lens.style.width = m.radius * 2 + "px";
    lens.style.height = m.radius * 2 + "px";
    lens.hidden = false;
  }

  function hide() {
    lens.hidden = true;
    mask.style.clipPath = "circle(0px at 50% 50%)";
    plate.style.transform = "none";
  }

  scan.addEventListener("pointermove", function (event) {
    if (event.pointerType === "touch") {
      if (event.pointerId !== touchId) return;
      event.preventDefault();
      place(event.clientX, event.clientY, true);
      return;
    }
    place(event.clientX, event.clientY, false);
  }, { passive: false });

  scan.addEventListener("pointerleave", function () {
    if (touchId !== null) return;
    hide();
  });

  scan.addEventListener("pointerdown", function (event) {
    if (event.pointerType === "mouse") return;
    event.preventDefault();
    touchId = event.pointerId;
    scan.setPointerCapture(event.pointerId);
    place(event.clientX, event.clientY, true);
  }, { passive: false });

  function endTouch(event) {
    if (event.pointerId !== touchId) return;
    touchId = null;
    hide();
  }

  scan.addEventListener("pointerup", endTouch);
  scan.addEventListener("pointercancel", endTouch);
})();

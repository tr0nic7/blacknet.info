(function () {
  var desktop = document.getElementById("desktop-fit");
  var mobile = document.getElementById("mobile-fit");
  var desktopStage = document.getElementById("desktop-stage");
  var mobileStage = document.getElementById("mobile-stage");
  var query = window.matchMedia("(max-width: 599px)");

  function fit(holder, stage, width, height) {
    var scale = window.innerWidth / width;
    stage.style.transform = "scale(" + scale + ")";
    holder.style.height = height * scale + "px";
  }

  function layout() {
    var phone = query.matches;
    desktop.hidden = phone;
    mobile.hidden = !phone;
    if (phone) {
      fit(mobile, mobileStage, 320, 572);
    } else {
      fit(desktop, desktopStage, 1024, 568);
    }
  }

  layout();
  window.addEventListener("resize", layout);
  query.addEventListener("change", layout);
})();

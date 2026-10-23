/* MuxWeb – Hero-Reveal: Porträt + Overlay-Ebene, die weich um den Cursor
   sichtbar wird (eigener Canvas-2D-Code, keine Bibliotheken). */
(function(){
  "use strict";
  // ---- Konfiguration (Bilder hier austauschen) ----
  var small = window.matchMedia("(max-width: 800px)").matches;
  var webp = document.createElement("canvas").toDataURL("image/webp").indexOf("data:image/webp") === 0;
  var ext = webp ? ".webp" : ".jpg";
  var CFG = {
    base:    "img/christoph" + (small ? "-800" : "") + ext + "?v=6", // Fallback / noscript
    overlay: "img/overlay"   + (small ? "-800" : "") + ext,
    // Animiertes Porträt (Distortion): Spritesheet. Rückgängig: sheet: "" setzen.
    sheet:   "img/christoph-sheet.webp?v=6",
    frames:  20,
    frameMs: 100,
    // Vorher (Stand 22.10. 20:45): radius 0.30, trail 0.03, ease 0.12, opacity 0.88, soft 0.6
    radius: 0.40,      // Reveal-Radius relativ zur Bildhöhe
    trail: 0.016,      // wie schnell die Spur verblasst (höher = schneller)
    ease: 0.075,       // Trägheit der Maske (niedriger = weicher, fluffiger)
    opacity: 0.92,     // max. Deckkraft der Overlay-Ebene (1 = voll deckend)
    soft: 0.42,        // ab wo der Rand weich ausläuft (niedriger = fluffigerer Rand)
    // Vorher (Stand 22.10. 21:50): wanderX 0.22, wanderY 0.12 -> zum Rückgängigmachen wieder eintragen
    wanderX: 0.36,     // wie weit die Haube seitlich vom Gesicht wegwandert (relativ zur Bildbreite)
    wanderY: 0.20,     // wie weit sie nach oben/unten wegwandert (relativ zur Bildhöhe)
    // Vorher (Stand 22.10. 21:52): pathSpeed 1 -> zum Rückgängigmachen wieder 1 eintragen
    pathSpeed: 0.7,    // Tempo der automatischen Bewegung (1 = vorher, kleiner = langsamer)
    // Kurze Pause, in der die Haube alles bedeckt (Stand 22.10. 21:53). Rückgängig: holdEvery: 0
    holdEvery: 12,     // alle X Sekunden kurz komplett bedeckt stehen bleiben (0 = aus)
    holdIn: 1.0,       // Sekunden, um weich in die Mitte zu gleiten
    hold: 1.2,         // Sekunden stehen bleiben
    holdOut: 1.0,      // Sekunden, um weich weiterzulaufen
    holdDrop: 0.06     // Pausenpunkt so weit tiefer als die Bahnmitte (deckt Kinn mit ab)
  };
  function holdAt(t){ // 0 = normale Bahn, 1 = steht in der Mitte (alles bedeckt)
    if (!CFG.holdEvery) return 0;
    var p = t % CFG.holdEvery, s = CFG.holdEvery - CFG.holdIn - CFG.hold - CFG.holdOut;
    if (p < s) return 0; p -= s;
    if (p < CFG.holdIn) return 0.5 - 0.5*Math.cos(Math.PI*p/CFG.holdIn); p -= CFG.holdIn;
    if (p < CFG.hold) return 1; p -= CFG.hold;
    return 0.5 + 0.5*Math.cos(Math.PI*p/CFG.holdOut);
  }
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- Name in Buchstaben zerlegen (Intro-Animation); .sq bleibt als Quadrat ----
  var nameEl = document.querySelector(".hero-name");
  if (nameEl) {
    var parts = Array.prototype.slice.call(nameEl.childNodes); nameEl.textContent = "";
    var ki = 0;
    parts.forEach(function(node){
      if (node.nodeType === 3) {
        node.textContent.split("").forEach(function(c){
          if (!c) return;
          var s = document.createElement("span"); s.className = "ch"; s.textContent = c;
          s.style.transitionDelay = (0.15 + ki*0.045) + "s"; s.style.setProperty("--k", ki); nameEl.appendChild(s); ki++;
        });
      } else if (node.nodeType === 1 && node.classList && node.classList.contains("sq")) {
        var s = document.createElement("span"); s.className = "ch ch-sq"; s.appendChild(node.cloneNode(true));
        s.style.transitionDelay = (0.15 + ki*0.045) + "s"; s.style.setProperty("--k", ki); nameEl.appendChild(s); ki++;
      } else if (node.nodeType === 1) {
        (node.textContent || "").split("").forEach(function(c){
          var s = document.createElement("span"); s.className = "ch"; s.textContent = c;
          s.style.transitionDelay = (0.15 + ki*0.045) + "s"; s.style.setProperty("--k", ki); nameEl.appendChild(s); ki++;
        });
      }
    });
  }
  // ---- Nav-Hover: Text in Zeichen splitten (zwei Reihen für 3D-Flug) ----
  document.querySelectorAll("[data-fly]").forEach(function(link){
    var txt = link.textContent, n = txt.length;
    link.setAttribute("aria-label", txt);
    link.textContent = "";
    var wrap = document.createElement("span"); wrap.className = "fly"; wrap.setAttribute("aria-hidden","true");
    function row(cls){
      var r = document.createElement("span"); r.className = "fly-row " + cls;
      txt.split("").forEach(function(ch, i){
        var c = document.createElement("span"); c.className = "c";
        c.textContent = ch === " " ? "\u00a0" : ch;
        c.style.setProperty("--i", i); c.style.setProperty("--j", n-1-i);
        r.appendChild(c);
      });
      return r;
    }
    var a = row("fly-a"); wrap.appendChild(a); wrap.appendChild(row("fly-b")); link.appendChild(wrap);
    function rnd(lo, hi){ return lo + Math.random()*(hi-lo); }
    function scatter(){ // neue Flugbahnen pro Hover
      a.querySelectorAll(".c").forEach(function(c, i){
        var side = (i - (n-1)/2) / n; // Richtung nach außen
        c.style.setProperty("--x", (side*70 + rnd(-10,10)).toFixed(1) + "px");
        c.style.setProperty("--y", rnd(-46,-18).toFixed(1) + "px");
        c.style.setProperty("--z", rnd(110,240).toFixed(0) + "px");
        c.style.setProperty("--rx", rnd(50,120).toFixed(0) + "deg");
        c.style.setProperty("--ry", (side*140 + rnd(-30,30)).toFixed(0) + "deg");
        c.style.setProperty("--rz", rnd(-25,25).toFixed(0) + "deg");
      });
    }
    scatter();
    link.addEventListener("mouseenter", scatter);
    link.addEventListener("focus", scatter);
    link._fly = function(){
      if (link.classList.contains("is-fly")) return;
      scatter(); void link.offsetWidth; link.classList.add("is-fly");
      setTimeout(function(){ link.classList.remove("is-fly"); }, 1500);
    };
    link.addEventListener("touchstart", function(){ link._fly(); }, {passive:true});
  });
  // Touch-Geräte: Nav-Links fliegen auch ohne Maus, beim Antippen und alle paar Sekunden automatisch
  if (window.matchMedia("(hover:none)").matches && !window.matchMedia("(prefers-reduced-motion:reduce)").matches){
    var flyLinks = Array.prototype.slice.call(document.querySelectorAll(".nav [data-fly]"));
    var flyLoop = function(){
      if (!document.hidden) flyLinks.forEach(function(l, k){ setTimeout(l._fly, k*450); });
    };
    setTimeout(flyLoop, 1200); setInterval(flyLoop, 5000);
  }

  // ---- Seitenübergang: Lime-Fläche wischt über den Viewport ----
  (function(){
    var wipe = document.getElementById("wipe"), label = document.getElementById("wipe-label");
    if (!wipe || !wipe.animate) return;
    var busy = false, EASE = "cubic-bezier(.76,0,.24,1)";
    var de = document.documentElement;
    function curY(){ return window.pageYOffset || de.scrollTop || document.body.scrollTop || 0; }
    // Robuster Sofort-Sprung (iOS/Android): smooth-Scrolling kurz aus, alle Scroll-Wurzeln setzen
    function jumpTo(y){
      var prev = de.style.scrollBehavior;
      de.style.scrollBehavior = "auto"; document.body.style.scrollBehavior = "auto";
      try { window.scrollTo(0, y); } catch(e){}
      de.scrollTop = y; document.body.scrollTop = y;
      de.style.scrollBehavior = prev; document.body.style.scrollBehavior = "";
    }
    document.querySelectorAll('.nav a[href^="#"], .footer a[href^="#"]').forEach(function(a){
      a.addEventListener("click", function(e){
        var id = a.getAttribute("href").slice(1), target = document.getElementById(id);
        if (!target || e.metaKey || e.ctrlKey || e.shiftKey) return;
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return; // normales Scrollen
        e.preventDefault(); if (busy) return; busy = true; wipe.style.visibility = "visible";
        var title = target.querySelector(".section-title"), isTop = (id === "top");
        label.textContent = a.getAttribute("data-wipe") || (isTop ? "//home" : (title ? title.textContent.trim() : "Christoph"));
        var reveals = isTop ? [] : target.querySelectorAll(".reveal");
        var lin = wipe.animate([{transform:"translateY(101%)"},{transform:"translateY(0)"}],
                               {duration:600, easing:EASE, fill:"forwards"});
        label.animate([{transform:"translateY(60%) scale(.9)",opacity:0},{transform:"none",opacity:1}],
                      {duration:500, delay:250, easing:"cubic-bezier(.2,.8,.2,1)", fill:"both"});
        var phase2Done = false;
        function phase2(){ if (phase2Done) return; phase2Done = true;
          // hinter der Fläche springen und Einblendungen zurücksetzen
          reveals.forEach(function(el){ el.style.transition="none"; el.classList.remove("in");
            el.querySelectorAll("li").forEach(function(li){ li.dataset.d = li.style.transitionDelay; li.style.transition="none"; }); });
          var top = isTop ? 0 : Math.round(target.getBoundingClientRect().top + curY());
          jumpTo(top);
          // Nachkontrolle im nächsten Frame (manche Mobil-Browser ignorieren den ersten Sprung)
          requestAnimationFrame(function(){ if (Math.abs(curY() - top) > 2) jumpTo(top); });
          try { if (history.pushState) history.pushState(null, "", isTop ? location.pathname + location.search : "#" + id); else location.hash = id; } catch(e){}
          void document.body.offsetHeight;
          reveals.forEach(function(el){ el.style.transition=""; el.querySelectorAll("li").forEach(function(li){ li.style.transition=""; }); });
          setTimeout(function(){
            if (Math.abs(curY() - top) > 2) jumpTo(top);
            var out = wipe.animate([{transform:"translateY(0)"},{transform:"translateY(-101%)"}],
                                   {duration:650, easing:EASE, fill:"forwards"});
            reveals.forEach(function(el, i){ setTimeout(function(){ el.classList.add("in"); }, 120 + i*90); });
            out.onfinish = function(){ wipe.style.visibility = "hidden"; lin.cancel(); out.cancel(); busy = false; };
          }, 280);
        }
        lin.onfinish = phase2;
        setTimeout(phase2, 750); // Fallback, falls onfinish nicht feuert
      });
    });
  })();

  // ---- Terminal-Zeile: Tipp-Animation (Text steht vollständig im HTML) ----
  (function(){
    var el = document.getElementById("term-cmd");
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var full = el.textContent, i = 0;
    el.setAttribute("aria-label", full);
    el.style.minWidth = el.offsetWidth + "px"; // Breite fixieren, kein Springen
    el.textContent = "";
    setTimeout(function tick(){
      el.textContent = full.slice(0, ++i);
      if (i < full.length) setTimeout(tick, 45 + Math.random()*70);
    }, 1200);
  })();

  var y = document.getElementById("year"); if (y) y.textContent = new Date().getFullYear();

  // ---- Scroll-Reveal ----
  var io = "IntersectionObserver" in window ? new IntersectionObserver(function(es){
    es.forEach(function(e){ if (e.isIntersecting){ e.target.classList.add("in"); io.unobserve(e.target);} });
  }, {threshold:0.15}) : null;
  document.querySelectorAll(".reveal").forEach(function(el){ io ? io.observe(el) : el.classList.add("in"); });
  // gestaffelte Einblendung der Kompetenz-Tags
  document.querySelectorAll(".skill-group").forEach(function(g, gi){
    g.querySelectorAll(".skill-list li").forEach(function(li, i){
      li.style.transitionDelay = (0.25 + gi*0.12 + i*0.07) + "s, " + (0.25 + gi*0.12 + i*0.07) + "s, 0s, 0s, 0s";
    });
  });

  // ---- Hero Canvas ----
  var hero = document.getElementById("hero");
  var cv = document.getElementById("hero-canvas");
  if (!cv || !cv.getContext) return;
  var ctx = cv.getContext("2d");
  var mask = document.createElement("canvas"), mctx = mask.getContext("2d");
  var layer = document.createElement("canvas"), lctx = layer.getContext("2d");
  var base = new Image(), over = new Image(), sheet = new Image(), loaded = 0, sheetReady = false, frameH = 0;
  var W=0,H=0,dpr=1, img={x:0,y:0,w:0,h:0};
  var target={x:-9999,y:-9999}, pos={x:-9999,y:-9999}, active=false, lastInput=0, visible=true;
  var MS = 0.5; // Masken-Auflösung (halbe Größe = schneller, weicher)

  function layout(){
    dpr = Math.min(window.devicePixelRatio||1, 2);
    W = hero.clientWidth; H = hero.clientHeight;
    cv.width = W*dpr; cv.height = H*dpr;
    layer.width = cv.width; layer.height = cv.height;
    mask.width = Math.ceil(W*MS); mask.height = Math.ceil(H*MS);
    if (!base.naturalWidth && !(sheetReady && sheet.naturalWidth)) return;
    var ar = (sheetReady ? sheet.naturalWidth/frameH : base.naturalWidth/base.naturalHeight);
    // Porträt: volle Höhe, Desktop rechts, Mobil zentriert & etwas höher
    var h = H, w = h*ar;
    if (W < 800 && H > W) { /* Hochformat: etwas kleiner, damit links/rechts die Bengalos sichtbar bleiben (vorher: Breite >= 105 %, Höhe >= 85 %) */ w = W*0.98; h = w/ar; if (h > H*0.7) { h = H*0.7; w = h*ar; } }
    var x = (W-w)/2; // horizontal zentriert
    var y = H-h;
    if (W < 800 && H > W) y = Math.min(H-h, Math.max(56, H*0.44 - h*0.42)); // Hochformat: Gesicht etwa auf 40 % der Höhe
    img = {x:x, y:y, w:w, h:h};
  }

  function stamp(x,y,r,a){
    var g = mctx.createRadialGradient(x*MS,y*MS,0,x*MS,y*MS,r*MS);
    g.addColorStop(0,"rgba(0,0,0,"+a+")");
    g.addColorStop(CFG.soft,"rgba(0,0,0,"+a+")");
    g.addColorStop(CFG.soft+(1-CFG.soft)*0.5,"rgba(0,0,0,"+(a*0.5)+")");
    g.addColorStop(CFG.soft+(1-CFG.soft)*0.8,"rgba(0,0,0,"+(a*0.15)+")");
    g.addColorStop(1,"rgba(0,0,0,0)");
    mctx.fillStyle = g;
    mctx.beginPath(); mctx.arc(x*MS,y*MS,r*MS,0,Math.PI*2); mctx.fill();
  }

  var t0 = performance.now();
  function frame(now){
    requestAnimationFrame(frame);
    if (!visible || loaded < 2) return;
    var t = (now - t0)/1000;
    // Ohne Eingabe (Touch/Idle): sanfte automatische Bahn über den Kopf
    if (!active || now - lastInput > 3500) {
      var cx = img.x + img.w*0.48, cy = img.y + img.h*0.36;
      target.x = cx + Math.sin(t*0.7*CFG.pathSpeed)*img.w*CFG.wanderX;
      target.y = cy + Math.sin(t*1.1*CFG.pathSpeed)*img.h*CFG.wanderY;
      var hw = holdAt(t); target.x += (cx - target.x)*hw; target.y += (cy + img.h*CFG.holdDrop - target.y)*hw;
    }
    var prevX = pos.x, prevY = pos.y;
    if (pos.x < -9000) { pos.x = target.x; pos.y = target.y; }
    pos.x += (target.x - pos.x)*CFG.ease;
    pos.y += (target.y - pos.y)*CFG.ease;
    var speed = Math.min(Math.hypot(pos.x-prevX, pos.y-prevY), 60);

    // Maske: alte Spur verblassen lassen, neuen weichen Punkt stempeln
    mctx.globalCompositeOperation = "destination-out";
    mctx.fillStyle = "rgba(0,0,0,"+CFG.trail+")";
    mctx.fillRect(0,0,mask.width,mask.height);
    mctx.globalCompositeOperation = "source-over";
    var r = img.h*CFG.radius*(1 + speed/120) * (1 + Math.sin(t*2.3)*0.04);
    // Zwischenpunkte für eine durchgehende Spur bei schnellen Bewegungen
    var steps = Math.max(1, Math.ceil(speed/12));
    for (var i=1;i<=steps;i++){
      var k=i/steps; stamp(prevX+(pos.x-prevX)*k, prevY+(pos.y-prevY)*k, r, 0.75);
    }

    // Zeichnen: Basisbild, dann maskierte Overlay-Ebene
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,W,H);
    // leichte Parallaxe zur Mausposition
    var px = (pos.x/W - 0.5)*-10, py = (pos.y/H - 0.5)*-6;
    hero.style.setProperty("--mx", (pos.x/W - 0.5).toFixed(3));
    hero.style.setProperty("--my", (pos.y/H - 0.5).toFixed(3));
    if (sheetReady) {
      var fi = Math.floor(now / CFG.frameMs) % CFG.frames;
      ctx.drawImage(sheet, 0, fi*frameH, sheet.naturalWidth, frameH, img.x+px, img.y+py, img.w, img.h);
    } else {
      ctx.drawImage(base, img.x+px, img.y+py, img.w, img.h);
    }

    lctx.setTransform(1,0,0,1,0,0);
    lctx.globalCompositeOperation = "source-over";
    lctx.clearRect(0,0,layer.width,layer.height);
    lctx.setTransform(dpr,0,0,dpr,0,0);
    lctx.drawImage(over, img.x+px, img.y+py, img.w, img.h);
    lctx.setTransform(1,0,0,1,0,0);
    lctx.globalCompositeOperation = "destination-in";
    lctx.drawImage(mask, 0,0, layer.width, layer.height);
    ctx.setTransform(1,0,0,1,0,0);
    ctx.globalAlpha = CFG.opacity;
    ctx.drawImage(layer,0,0);
    ctx.globalAlpha = 1;
    edgeFade(px);

    // Akzent-Ring am Cursor (nur Desktop)
    if (active && now - lastInput < 3500 && window.matchMedia("(hover:hover)").matches){
      ctx.setTransform(dpr,0,0,dpr,0,0);
      ctx.strokeStyle="rgba(212,255,58,.55)"; ctx.lineWidth=1;
      ctx.beginPath(); ctx.arc(pos.x,pos.y,r*0.6,0,Math.PI*2); ctx.stroke();
    }
  }

  function edgeFade(px){ // weicher, transparenter Übergang an den Bildrändern (Rauch-Ebene scheint durch)
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.globalCompositeOperation = "destination-out";
    var x0 = img.x + (px||0), x1 = x0 + img.w, f = img.w*0.22, g;
    if (x0 > -f) {
      if (x0 > 0) ctx.clearRect(0,0,x0+1,H);
      g = ctx.createLinearGradient(x0,0,x0+f,0);
      g.addColorStop(0,"rgba(0,0,0,1)"); g.addColorStop(1,"rgba(0,0,0,0)");
      ctx.fillStyle=g; ctx.fillRect(x0,0,f,H);
    }
    if (x1 < W + f) {
      if (x1 < W) ctx.clearRect(x1-1,0,W-x1+1,H);
      g = ctx.createLinearGradient(x1,0,x1-f,0);
      g.addColorStop(0,"rgba(0,0,0,1)"); g.addColorStop(1,"rgba(0,0,0,0)");
      ctx.fillStyle=g; ctx.fillRect(x1-f,0,f,H);
    }
    // oberer Rand weich ausblenden
    var y0 = img.y, ft = img.h*0.12;
    g = ctx.createLinearGradient(0,y0,0,y0+ft);
    g.addColorStop(0,"rgba(0,0,0,1)"); g.addColorStop(1,"rgba(0,0,0,0)");
    ctx.fillStyle=g; ctx.fillRect(0,y0,W,ft);
    if (y0 > 0) ctx.clearRect(0,0,W,y0+1);
    ctx.globalCompositeOperation = "source-over";
  }

  function staticDraw(){ // reduzierte Bewegung: nur Basisbild
    if (loaded<2) return; layout();
    ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,W,H);
    if (sheetReady) ctx.drawImage(sheet,0,0,sheet.naturalWidth,frameH,img.x,img.y,img.w,img.h);
    else ctx.drawImage(base,img.x,img.y,img.w,img.h); edgeFade(0);
  }

  function setPointer(cx,cy){
    var b = cv.getBoundingClientRect();
    target.x = cx-b.left; target.y = cy-b.top; active = true; lastInput = performance.now();
  }
  hero.addEventListener("pointermove", function(e){ setPointer(e.clientX,e.clientY); }, {passive:true});
  hero.addEventListener("pointerdown", function(e){ setPointer(e.clientX,e.clientY); }, {passive:true});
  hero.addEventListener("touchmove", function(e){ var p=e.touches[0]; if(p) setPointer(p.clientX,p.clientY); }, {passive:true});
  hero.addEventListener("pointerleave", function(){ active=false; });

  if ("IntersectionObserver" in window)
    new IntersectionObserver(function(es){ visible = es[0].isIntersecting; }).observe(hero);

  var rt; window.addEventListener("resize", function(){ clearTimeout(rt); rt=setTimeout(function(){ reduced?staticDraw():layout(); },120); });
  // iOS: nach dem Drehen stimmen die Maße oft erst etwas später, deshalb nochmal nachmessen
  window.addEventListener("orientationchange", function(){ [150,450,900].forEach(function(d){ setTimeout(function(){ reduced?staticDraw():layout(); }, d); }); });
  if (window.visualViewport) visualViewport.addEventListener("resize", function(){ clearTimeout(rt); rt=setTimeout(function(){ reduced?staticDraw():layout(); },150); });

  function maybeStart(){
    if (loaded < 2) return;
    if (CFG.sheet && !sheetReady && !sheet.complete) return;
    layout(); document.body.classList.add("loaded");
    if (reduced) staticDraw(); else requestAnimationFrame(frame);
  }
  function onload(){ loaded++; maybeStart(); }
  base.onload = over.onload = onload;
  base.onerror = function(){ document.body.classList.add("loaded"); };
  base.src = CFG.base; over.src = CFG.overlay;
  if (CFG.sheet) {
    sheet.onload = function(){ frameH = sheet.naturalHeight / CFG.frames; sheetReady = true; maybeStart(); };
    sheet.onerror = function(){ sheetReady = false; maybeStart(); };
    sheet.src = CFG.sheet;
  }
  setTimeout(function(){ document.body.classList.add("loaded"); }, 2500);
})();

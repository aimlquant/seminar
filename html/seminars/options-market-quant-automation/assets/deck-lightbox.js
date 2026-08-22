/* AIML Quant deck image viewer: click / keyboard / wheel / pinch */
(function () {
  "use strict";

  const targets = Array.from(document.querySelectorAll(".slide img, .slide svg[data-deck-zoom]"))
    .filter((target) => !target.closest("a") && !target.closest(".deck-lightbox"));
  if (!targets.length) return;

  const lightbox = document.createElement("div");
  lightbox.className = "deck-lightbox";
  lightbox.setAttribute("role", "dialog");
  lightbox.setAttribute("aria-modal", "true");
  lightbox.setAttribute("aria-hidden", "true");
  lightbox.hidden = true;
  lightbox.innerHTML =
    '<div class="deck-lightbox__toolbar">' +
      '<strong class="deck-lightbox__title" id="deckLightboxTitle"></strong>' +
      '<div class="deck-lightbox__actions">' +
        '<button type="button" data-deck-lightbox-action="zoom-out" aria-label="축소" title="축소 (−)">−</button>' +
        '<output class="deck-lightbox__scale" aria-live="polite">100%</output>' +
        '<button type="button" data-deck-lightbox-action="zoom-in" aria-label="확대" title="확대 (+)">+</button>' +
        '<button type="button" data-deck-lightbox-action="reset" aria-label="화면에 맞춤" title="화면에 맞춤 (0)">1:1</button>' +
        '<button type="button" data-deck-lightbox-action="fullscreen" aria-label="브라우저 전체화면" aria-pressed="false" title="브라우저 전체화면">⛶</button>' +
        '<button type="button" data-deck-lightbox-action="close" aria-label="닫기" title="닫기 (Esc)">×</button>' +
      '</div>' +
    '</div>' +
    '<div class="deck-lightbox__viewport" tabindex="0"><div class="deck-lightbox__stage"></div></div>' +
    '<p class="deck-lightbox__hint">휠·+/− 확대 · 드래그 이동 · 더블클릭 전환 · 핀치 줌 · Esc 닫기</p>';
  document.body.appendChild(lightbox);

  const viewport = lightbox.querySelector(".deck-lightbox__viewport");
  const stage = lightbox.querySelector(".deck-lightbox__stage");
  const title = lightbox.querySelector(".deck-lightbox__title");
  const scaleOutput = lightbox.querySelector(".deck-lightbox__scale");
  const closeButton = lightbox.querySelector('[data-deck-lightbox-action="close"]');
  const fullscreenButton = lightbox.querySelector('[data-deck-lightbox-action="fullscreen"]');
  const pointers = new Map();
  let visual = null;
  let lastFocus = null;
  let scale = 1;
  let panX = 0;
  let panY = 0;
  let dragStart = null;
  let pinchStart = null;
  let didMove = false;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  function getLabel(target) {
    const item = target.closest(".deck-figure-pair__item");
    const figure = target.closest("figure");
    const itemTitle = item?.querySelector("strong")?.textContent.trim();
    const figureTitle = figure?.dataset.deckFigureTitle;
    const figureNumber = figure?.dataset.deckFigureNumber;
    if (itemTitle) return itemTitle;
    if (figureTitle && figureNumber) return `그림 ${figureNumber} · ${figureTitle}`;
    return figureTitle || target.getAttribute("alt") || "확대 이미지";
  }

  function constrainPan() {
    if (!visual || scale <= 1) {
      panX = 0;
      panY = 0;
      return;
    }
    const width = visual.offsetWidth * scale;
    const height = visual.offsetHeight * scale;
    const maxX = Math.max(0, (width - viewport.clientWidth) / 2 + viewport.clientWidth * 0.2);
    const maxY = Math.max(0, (height - viewport.clientHeight) / 2 + viewport.clientHeight * 0.2);
    panX = clamp(panX, -maxX, maxX);
    panY = clamp(panY, -maxY, maxY);
  }

  function render() {
    constrainPan();
    stage.style.transform =
      `translate(calc(-50% + ${panX}px), calc(-50% + ${panY}px)) scale(${scale})`;
    scaleOutput.textContent = `${Math.round(scale * 100)}%`;
    viewport.classList.toggle("is-zoomed", scale > 1);
  }

  function resetView() {
    scale = 1;
    panX = 0;
    panY = 0;
    render();
  }

  function zoomAt(nextScale, clientX, clientY) {
    const next = clamp(nextScale, 1, 6);
    if (next === scale) return;
    const rect = viewport.getBoundingClientRect();
    const x = typeof clientX === "number" ? clientX - rect.left - rect.width / 2 : 0;
    const y = typeof clientY === "number" ? clientY - rect.top - rect.height / 2 : 0;
    const worldX = (x - panX) / scale;
    const worldY = (y - panY) / scale;
    panX = x - worldX * next;
    panY = y - worldY * next;
    scale = next;
    render();
  }

  function openLightbox(target) {
    lastFocus = document.activeElement;
    visual = target.tagName.toLowerCase() === "img"
      ? Object.assign(document.createElement("img"), {
          src: target.currentSrc || target.src,
          alt: target.alt || "",
          decoding: "async"
        })
      : target.cloneNode(true);
    visual.removeAttribute?.("data-deck-zoomable");
    visual.removeAttribute?.("tabindex");
    visual.removeAttribute?.("role");
    visual.classList.add("deck-lightbox__visual");
    visual.setAttribute("draggable", "false");
    stage.replaceChildren(visual);
    title.textContent = getLabel(target);
    lightbox.setAttribute("aria-labelledby", "deckLightboxTitle");
    lightbox.setAttribute("aria-hidden", "false");
    lightbox.hidden = false;
    document.body.classList.add("deck-lightbox-open");
    resetView();
    requestAnimationFrame(() => {
      lightbox.classList.add("is-open");
      closeButton.focus({ preventScroll: true });
    });
  }

  function closeLightbox() {
    if (lightbox.hidden) return;
    lightbox.classList.remove("is-open");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.classList.remove("deck-lightbox-open");
    if (document.fullscreenElement === lightbox) {
      document.exitFullscreen?.().catch(() => {});
    }
    lightbox.hidden = true;
    stage.replaceChildren();
    visual = null;
    pointers.clear();
    dragStart = null;
    pinchStart = null;
    lastFocus?.focus?.({ preventScroll: true });
  }

  targets.forEach((target) => {
    target.dataset.deckZoomable = "true";
    target.tabIndex = 0;
    target.setAttribute("role", "button");
    target.setAttribute("aria-haspopup", "dialog");
    target.setAttribute("aria-label", `${getLabel(target)} — 전체화면으로 확대`);
    target.title ||= "클릭하여 전체화면으로 확대";
    target.addEventListener("click", () => openLightbox(target));
    target.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openLightbox(target);
      }
    });
    target.addEventListener("dragstart", (event) => event.preventDefault());
  });

  lightbox.addEventListener("click", (event) => {
    event.stopPropagation();
    const control = event.target.closest("[data-deck-lightbox-action]");
    if (!control) return;
    const action = control.dataset.deckLightboxAction;
    if (action === "close") closeLightbox();
    if (action === "zoom-in") zoomAt(scale + 0.25);
    if (action === "zoom-out") zoomAt(scale - 0.25);
    if (action === "reset") resetView();
    if (action === "fullscreen") {
      if (document.fullscreenElement) {
        document.exitFullscreen?.().catch(() => {});
      } else {
        lightbox.requestFullscreen?.({ navigationUI: "hide" }).catch(() => {});
      }
    }
  });

  lightbox.addEventListener("touchstart", (event) => event.stopPropagation(), { passive: true });
  lightbox.addEventListener("touchend", (event) => event.stopPropagation(), { passive: true });

  viewport.addEventListener("wheel", (event) => {
    event.preventDefault();
    zoomAt(scale * (event.deltaY < 0 ? 1.15 : 1 / 1.15), event.clientX, event.clientY);
  }, { passive: false });

  viewport.addEventListener("dblclick", (event) => {
    event.preventDefault();
    zoomAt(scale > 1 ? 1 : 2, event.clientX, event.clientY);
  });

  viewport.addEventListener("click", (event) => {
    if (event.target === viewport && !didMove) closeLightbox();
    didMove = false;
  });

  viewport.addEventListener("pointerdown", (event) => {
    viewport.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    didMove = false;
    if (pointers.size === 1) {
      dragStart = { x: event.clientX, y: event.clientY, panX, panY };
      pinchStart = null;
    } else if (pointers.size === 2) {
      const pair = Array.from(pointers.values());
      pinchStart = {
        distance: Math.hypot(pair[1].x - pair[0].x, pair[1].y - pair[0].y) || 1,
        scale,
        panX,
        panY,
        x: (pair[0].x + pair[1].x) / 2,
        y: (pair[0].y + pair[1].y) / 2
      };
      dragStart = null;
    }
    viewport.classList.add("is-dragging");
  });

  viewport.addEventListener("pointermove", (event) => {
    if (!pointers.has(event.pointerId)) return;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.size === 1 && dragStart && scale > 1) {
      panX = dragStart.panX + event.clientX - dragStart.x;
      panY = dragStart.panY + event.clientY - dragStart.y;
      didMove ||= Math.abs(event.clientX - dragStart.x) + Math.abs(event.clientY - dragStart.y) > 6;
      render();
    } else if (pointers.size === 2 && pinchStart) {
      const pair = Array.from(pointers.values());
      const midpointX = (pair[0].x + pair[1].x) / 2;
      const midpointY = (pair[0].y + pair[1].y) / 2;
      const rect = viewport.getBoundingClientRect();
      const startX = pinchStart.x - rect.left - rect.width / 2;
      const startY = pinchStart.y - rect.top - rect.height / 2;
      const nowX = midpointX - rect.left - rect.width / 2;
      const nowY = midpointY - rect.top - rect.height / 2;
      const worldX = (startX - pinchStart.panX) / pinchStart.scale;
      const worldY = (startY - pinchStart.panY) / pinchStart.scale;
      scale = clamp(
        pinchStart.scale *
          (Math.hypot(pair[1].x - pair[0].x, pair[1].y - pair[0].y) / pinchStart.distance),
        1,
        6
      );
      panX = nowX - worldX * scale;
      panY = nowY - worldY * scale;
      didMove = true;
      render();
    }
  });

  function releasePointer(event) {
    pointers.delete(event.pointerId);
    if (pointers.size === 1) {
      const remaining = Array.from(pointers.values())[0];
      dragStart = { x: remaining.x, y: remaining.y, panX, panY };
    } else {
      dragStart = null;
    }
    pinchStart = null;
    if (!pointers.size) viewport.classList.remove("is-dragging");
  }

  viewport.addEventListener("pointerup", releasePointer);
  viewport.addEventListener("pointercancel", releasePointer);

  document.addEventListener("keydown", (event) => {
    if (lightbox.hidden) return;
    event.stopImmediatePropagation();
    if (event.key === "Escape") {
      event.preventDefault();
      closeLightbox();
    } else if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      zoomAt(scale + 0.25);
    } else if (event.key === "-") {
      event.preventDefault();
      zoomAt(scale - 0.25);
    } else if (event.key === "0") {
      event.preventDefault();
      resetView();
    } else if (event.key.startsWith("Arrow") && scale > 1) {
      event.preventDefault();
      const distance = event.shiftKey ? 96 : 48;
      if (event.key === "ArrowLeft") panX += distance;
      if (event.key === "ArrowRight") panX -= distance;
      if (event.key === "ArrowUp") panY += distance;
      if (event.key === "ArrowDown") panY -= distance;
      render();
    } else if (event.key === "Tab") {
      const focusable = Array.from(lightbox.querySelectorAll("button, [tabindex='0']"));
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }, true);

  document.addEventListener("fullscreenchange", () => {
    const active = document.fullscreenElement === lightbox;
    fullscreenButton.setAttribute("aria-pressed", String(active));
    fullscreenButton.title = active ? "전체화면 종료" : "브라우저 전체화면";
  });
  window.addEventListener("resize", render);
})();

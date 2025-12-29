// DASHBOARD DRAG-TO-SCROLL
document.addEventListener("DOMContentLoaded", () => {
  // Target all horizontal scrollers on the dashboard
  const scrollers = document.querySelectorAll(".dashboard-scroll");

  scrollers.forEach((el) => {
    // Drag state
    let isDown = false;
    let startX = 0;
    let startScrollLeft = 0;
    let hasDragged = false;

    // Minimum movement before treating as a drag
    const DRAG_THRESHOLD = 6;

    // Start drag on left mouse button press
    el.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;

      isDown = true;
      hasDragged = false;

      startX = e.pageX;
      startScrollLeft = el.scrollLeft;
    });

    // Update scroll position while dragging
    el.addEventListener("mousemove", (e) => {
      if (!isDown) return;

      const walk = e.pageX - startX;

      // Only trigger drag behaviour after threshold is exceeded
      if (Math.abs(walk) > DRAG_THRESHOLD) {
        hasDragged = true;
        el.classList.add("is-dragging");
        e.preventDefault();
        el.scrollLeft = startScrollLeft - walk;
      }
    });

    // End drag and reset UI state
    const endDrag = () => {
      isDown = false;
      el.classList.remove("is-dragging");
    };

    // End drag on mouse release anywhere, or when leaving the scroller
    window.addEventListener("mouseup", endDrag);
    el.addEventListener("mouseleave", endDrag);

    // Prevent clicks firing after a drag
    el.addEventListener(
      "click",
      (e) => {
        if (hasDragged) {
          e.preventDefault();
          e.stopPropagation();
          hasDragged = false;
        }
      },
      true
    );
  });
});

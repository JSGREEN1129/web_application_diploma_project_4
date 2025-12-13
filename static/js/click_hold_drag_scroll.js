document.addEventListener("DOMContentLoaded", () => {
  const scrollers = document.querySelectorAll(".dashboard-scroll");

  scrollers.forEach((el) => {
    let isDown = false;
    let startX = 0;
    let startScrollLeft = 0;
    let hasDragged = false;

    const DRAG_THRESHOLD = 6;

    el.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      isDown = true;
      hasDragged = false;

      startX = e.pageX;
      startScrollLeft = el.scrollLeft;
    });

    el.addEventListener("mousemove", (e) => {
      if (!isDown) return;

      const walk = e.pageX - startX;

      if (Math.abs(walk) > DRAG_THRESHOLD) {
        hasDragged = true;
        el.classList.add("is-dragging");
        e.preventDefault();
        el.scrollLeft = startScrollLeft - walk;
      }
    });

    const endDrag = () => {
      isDown = false;
      el.classList.remove("is-dragging");
    };

    window.addEventListener("mouseup", endDrag);
    el.addEventListener("mouseleave", endDrag);

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

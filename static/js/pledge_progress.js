(function () {
  const input = document.querySelector(".js-pledge-amount");
  if (!input) return;

  function setEstimate(id, text) {
    const el = document.querySelector(`.js-return-estimate[data-listing-id="${id}"]`);
    if (el) el.textContent = text;
  }

  let timer = null;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const val = input.value.trim();
      if (!val) return;
      const res = await fetch(input.dataset.estimateUrl + "?amount=" + val);
      const data = await res.json();
      if (data.ok) {
        setEstimate(input.dataset.listingId,
          `Estimated return: £${data.total_min}–£${data.total_max}`);
      }
    }, 300);
  });
})();
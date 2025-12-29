// PLEDGE RETURN ESTIMATE
(function () {
  // Pledge amount input
  const input = document.querySelector(".js-pledge-amount");
  if (!input) return;

  // Update the return estimate text for a listing
  function setEstimate(id, text) {
    const el = document.querySelector(`.js-return-estimate[data-listing-id="${id}"]`);
    if (el) el.textContent = text;
  }

  // Debounce timer for API calls
  let timer = null;

  // Listen for changes to the pledge amount
  input.addEventListener("input", () => {
    clearTimeout(timer);

    timer = setTimeout(async () => {
      const val = input.value.trim();
      if (!val) return;

      // Fetch estimated return for the entered amount
      const res = await fetch(input.dataset.estimateUrl + "?amount=" + val);
      const data = await res.json();

      // Update estimate if response is valid
      if (data.ok) {
        setEstimate(
          input.dataset.listingId,
          `Estimated return: £${data.total_min}–£${data.total_max}`
        );
      }
    }, 300);
  });
})();

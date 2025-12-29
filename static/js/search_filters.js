// SEARCH FILTER CASCADE: COUNTRY → COUNTY → POSTCODE PREFIX
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    // API endpoints from data attributes
    const endpointsEl = document.getElementById("js-search-endpoints");
    if (!endpointsEl) return;

    const countiesUrl = endpointsEl.dataset.countiesUrl;
    const outcodesUrl = endpointsEl.dataset.outcodesUrl;

    if (!countiesUrl || !outcodesUrl) return;

    // Search form selects
    const countryEl = document.getElementById("id_country");
    const countyEl = document.getElementById("id_county");
    const outcodeEl = document.getElementById("id_postcode_prefix");

    if (!countryEl || !countyEl || !outcodeEl) return;

    // Reset a select to a single placeholder option
    function resetSelect(el, placeholder) {
      el.innerHTML = "";
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = placeholder;
      el.appendChild(opt);
    }

    // Load counties for a selected country
    async function loadCounties(countryValue, selectedCounty) {
      resetSelect(countyEl, "Any county");
      resetSelect(outcodeEl, "Any prefix");
      countyEl.disabled = true;
      outcodeEl.disabled = true;

      if (!countryValue) return;

      const url =
        countiesUrl +
        "?country=" +
        encodeURIComponent(countryValue.toLowerCase());

      const res = await fetch(url);
      const data = await res.json();

      (data.counties || []).forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c;
        opt.textContent = c;
        if (selectedCounty && selectedCounty === c) opt.selected = true;
        countyEl.appendChild(opt);
      });

      countyEl.disabled = false;

      // If a county is preselected, load its outcodes too
      if (selectedCounty) {
        await loadOutcodes(selectedCounty, outcodeEl.dataset.selected || "");
      }
    }

    // Load postcode prefixes for a selected county
    async function loadOutcodes(countyValue, selectedOutcode) {
      resetSelect(outcodeEl, "Any prefix");
      outcodeEl.disabled = true;

      if (!countyValue) return;

      const url =
        outcodesUrl + "?county=" + encodeURIComponent(countyValue);

      const res = await fetch(url);
      const data = await res.json();

      (data.outcodes || []).forEach((o) => {
        const opt = document.createElement("option");
        opt.value = o;
        opt.textContent = o;
        if (selectedOutcode && selectedOutcode === o) opt.selected = true;
        outcodeEl.appendChild(opt);
      });

      outcodeEl.disabled = false;
    }

    // User-driven changes
    countryEl.addEventListener("change", function () {
      loadCounties(countryEl.value, "");
    });

    countyEl.addEventListener("change", function () {
      loadOutcodes(countyEl.value, "");
    });

    // Initial hydrate (preserve selected values where available)
    const selectedCountry =
      countryEl.dataset.selected || countryEl.value || "";
    const selectedCounty = countyEl.dataset.selected || "";
    const selectedOutcode = outcodeEl.dataset.selected || "";

    if (selectedCountry) {
      countryEl.value = selectedCountry;
      outcodeEl.dataset.selected = selectedOutcode;
      loadCounties(selectedCountry, selectedCounty);
    } else {
      resetSelect(countyEl, "Any county");
      resetSelect(outcodeEl, "Any prefix");
    }
  });
})();

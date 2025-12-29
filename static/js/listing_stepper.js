// EDIT LISTING HELPERS
document.addEventListener("DOMContentLoaded", function () {
  // COUNTRY AND COUNTY AND OUTCODE CASCADE
  (function () {
    // Form selects
    const countryEl = document.getElementById("id_country");
    const countyEl = document.getElementById("id_county");
    const outcodeEl = document.getElementById("id_postcode_prefix");

    // API endpoints from data attributes
    const endpointsEl = document.getElementById("js-listing-endpoints");
    const COUNTIES_URL = endpointsEl?.dataset?.countiesUrl || "";
    const OUTCODES_URL = endpointsEl?.dataset?.outcodesUrl || "";

    // Pre-saved values for edit flows
    const stateEl = document.getElementById("js-listing-state");
    const savedCountry = (stateEl?.dataset?.country || "").trim();
    const savedCounty = (stateEl?.dataset?.county || "").trim();
    const savedOutcode = (stateEl?.dataset?.outcode || "").trim();

    // Initial values
    const initialCountry = String(countryEl?.value || countryEl?.dataset?.selected || savedCountry || "").trim();
    const initialCounty = String(countyEl?.value || countyEl?.dataset?.selected || savedCounty || "").trim();
    const initialOutcode = String(outcodeEl?.value || outcodeEl?.dataset?.selected || savedOutcode || "").trim();

    // Replace a select’s options and optionally select a value
    function setOptions(selectEl, items, placeholder, selectedValue = "") {
      if (!selectEl) return;
      selectEl.innerHTML = "";

      const opt0 = document.createElement("option");
      opt0.value = "";
      opt0.textContent = placeholder;
      selectEl.appendChild(opt0);

      (items || []).forEach((v) => {
        const opt = document.createElement("option");
        opt.value = v;
        opt.textContent = v;
        if (selectedValue && v === selectedValue) opt.selected = true;
        selectEl.appendChild(opt);
      });

      // Extra safety: force value after options exist
      if (selectedValue) selectEl.value = selectedValue;
    }

    // Load postcode prefixes for a selected county
    async function loadOutcodes(selectedOutcode = "", countyOverride = "") {
      const county = (countyOverride || countyEl?.value || "").trim();

      // Reset outcodes when county changes
      setOptions(outcodeEl, [], "Select postcode prefix");
      window.gscEditListingSync?.();

      if (!county || !OUTCODES_URL) return;

      const res = await fetch(OUTCODES_URL + "?county=" + encodeURIComponent(county));
      if (!res.ok) return;

      const data = await res.json();
      setOptions(outcodeEl, data.outcodes || [], "Select postcode prefix", selectedOutcode);

      window.gscEditListingSync?.();
    }

    // Load counties for a selected country
    async function loadCounties(selectedCounty = "") {
      const country = (countryEl?.value || "").trim();

      // Reset dependent selects when country changes
      setOptions(countyEl, [], "Select county");
      setOptions(outcodeEl, [], "Select postcode prefix");
      window.gscEditListingSync?.();

      if (!country || !COUNTIES_URL) return;

      const res = await fetch(COUNTIES_URL + "?country=" + encodeURIComponent(country));
      if (!res.ok) return;

      const data = await res.json();
      setOptions(countyEl, data.counties || [], "Select county", selectedCounty);

      window.gscEditListingSync?.();

      // If we have a county, load outcodes and preserve the initial outcode where possible
      const countyNow = (selectedCounty || countyEl?.value || "").trim();
      if (countyNow) {
        countyEl.value = countyNow;
        await loadOutcodes(initialOutcode, countyNow);
        window.gscEditListingSync?.();
      }
    }

    // User-driven changes
    countryEl?.addEventListener("change", () => loadCounties(""));
    countyEl?.addEventListener("change", () => loadOutcodes("", (countyEl?.value || "").trim()));

    // Initial hydrate (edit mode and persisted state)
    if (initialCountry) {
      countryEl.value = initialCountry;
      loadCounties(initialCounty);
    } else {
      setOptions(countyEl, [], "Select county");
      setOptions(outcodeEl, [], "Select postcode prefix");
    }
  })();

  // STEPPER AND ACTIVATE BUTTON GATING
  (function () {
    // Stepper pill elements
    const stepper = {
      s1: document.getElementById("js-stepper-1"),
      s2: document.getElementById("js-stepper-2"),
      s3: document.getElementById("js-stepper-3"),
      s4: document.getElementById("js-stepper-4"),
      s5: document.getElementById("js-stepper-5"),
      s6: document.getElementById("js-stepper-6"),
      msg: document.getElementById("js-stepper-msg"),
    };

    // Card header pills (Conforms to the stepper status)
    const cards = {
      c1: document.getElementById("js-card-1"),
      c2: document.getElementById("js-card-2"),
      c3: document.getElementById("js-card-3"),
      c4: document.getElementById("js-card-4"),
      c5: document.getElementById("js-card-5"),
      c6: document.getElementById("js-card-6"),
      msg6: document.getElementById("js-step6-msg"),
    };

    // Activation button (enabled only when all steps are complete)
    const activateBtn = document.getElementById("js-activate-btn");

    // Required fields for each step
    const required = {
      step1: ["#id_project_duration_days"],
      step2: ["#id_source_use", "#id_target_use"],
      step3: ["#id_funding_band", "#id_return_type", "#id_return_band", "#id_duration_days"],
      step4: ["#id_country", "#id_county", "#id_postcode_prefix"],
    };

    // Media inputs (step 5)
    const imgInput = document.getElementById("id_images");
    const docInput = document.getElementById("id_documents");

    // Check if a field has a non-empty value
    function hasValue(sel) {
      const el = document.querySelector(sel);
      if (!el) return false;
      return String(el.value || "").trim() !== "";
    }

    // Validate a full step
    function stepOk(selectors) {
      return (selectors || []).every(hasValue);
    }

    // Step 5: at least one media file added
    function mediaSelected() {
      const imgCount = imgInput?.files?.length || 0;
      const docCount = docInput?.files?.length || 0;
      return imgCount + docCount > 0;
    }

    // Apply success and neutral classes to a pill element
    function setPill(el, ok) {
      if (!el) return;
      el.classList.remove("bg-success", "text-white", "bg-light", "text-dark", "border");
      if (ok) el.classList.add("bg-success", "text-white");
      else el.classList.add("bg-light", "text-dark", "border");
    }

    // Sync UI state for stepper, cards, and activation button
    function sync() {
      const ok1 = stepOk(required.step1);
      const ok2 = stepOk(required.step2);
      const ok3 = stepOk(required.step3);
      const ok4 = stepOk(required.step4);
      const ok5 = mediaSelected();
      const okAll = ok1 && ok2 && ok3 && ok4 && ok5;

      setPill(stepper.s1, ok1); setPill(cards.c1, ok1);
      setPill(stepper.s2, ok2); setPill(cards.c2, ok2);
      setPill(stepper.s3, ok3); setPill(cards.c3, ok3);
      setPill(stepper.s4, ok4); setPill(cards.c4, ok4);
      setPill(stepper.s5, ok5); setPill(cards.c5, ok5);
      setPill(stepper.s6, okAll); setPill(cards.c6, okAll);

      // Stepper message
      if (stepper.msg) {
        stepper.msg.classList.remove("text-success", "text-muted");
        if (okAll) {
          stepper.msg.textContent = "Steps 1–5 complete — activation is available.";
          stepper.msg.classList.add("text-success");
        } else {
          stepper.msg.textContent = "Complete steps 1–5 to enable activation. You can save a draft at any time.";
          stepper.msg.classList.add("text-muted");
        }
      }

      // Step 6 message
      if (cards.msg6) {
        cards.msg6.classList.remove("text-success", "text-muted");
        if (okAll) {
          cards.msg6.textContent = "Ready to activate — you’ll be taken to payment.";
          cards.msg6.classList.add("text-success");
        } else if (!ok5) {
          cards.msg6.textContent = "Upload at least one image or document to complete Step 5.";
          cards.msg6.classList.add("text-muted");
        } else {
          cards.msg6.textContent = "Complete Steps 1–5 to enable activation.";
          cards.msg6.classList.add("text-muted");
        }
      }

      // Activate button enabled only when all steps are complete
      if (activateBtn) {
        activateBtn.disabled = !okAll;
      }
    }

    // Expose sync so other scripts can trigger updates
    window.gscEditListingSync = sync;

    // Watch required fields for changes
    const watch = [
      ...required.step1, ...required.step2, ...required.step3, ...required.step4,
    ];

    watch.forEach((sel) => {
      const el = document.querySelector(sel);
      el?.addEventListener("change", sync);
      el?.addEventListener("input", sync);
    });

    // Watch media inputs
    imgInput?.addEventListener("change", sync);
    docInput?.addEventListener("change", sync);

    // Initial render
    sync();
  })();
});

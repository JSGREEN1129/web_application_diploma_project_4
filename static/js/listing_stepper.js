(function () {
  const countryEl = document.getElementById("id_country");
  const countyEl = document.getElementById("id_county");
  const outcodeEl = document.getElementById("id_postcode_prefix");

  const endpointsEl = document.getElementById("js-listing-endpoints");
  const COUNTIES_URL = endpointsEl?.dataset?.countiesUrl || "";
  const OUTCODES_URL = endpointsEl?.dataset?.outcodesUrl || "";

  const initialCountry = (countryEl?.dataset?.selected || "").trim();
  const initialCounty = (countyEl?.dataset?.selected || "").trim();
  const initialOutcode = (outcodeEl?.dataset?.selected || "").trim();

  function setOptions(selectEl, items, placeholder, selectedValue = "") {
    if (!selectEl) return;
    selectEl.innerHTML = "";

    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = placeholder;
    selectEl.appendChild(opt0);

    (items || []).forEach(v => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      if (selectedValue && v === selectedValue) opt.selected = true;
      selectEl.appendChild(opt);
    });
  }

  async function loadCounties(selectedCounty = "") {
    const country = (countryEl?.value || "").trim();

    setOptions(countyEl, [], "Select county");
    setOptions(outcodeEl, [], "Select postcode prefix");

    window.gscEditListingSync?.();

    if (!country || !COUNTIES_URL) return;

    const res = await fetch(COUNTIES_URL + "?country=" + encodeURIComponent(country));
    if (!res.ok) return;

    const data = await res.json();
    setOptions(countyEl, data.counties || [], "Select county", selectedCounty);

    window.gscEditListingSync?.();

    const countyNow = (countyEl?.value || "").trim();
    if (countyNow) {
      await loadOutcodes(selectedCounty ? initialOutcode : "");
      window.gscEditListingSync?.();
    }
  }

  async function loadOutcodes(selectedOutcode = "") {
    const county = (countyEl?.value || "").trim();
    setOptions(outcodeEl, [], "Select postcode prefix");

    window.gscEditListingSync?.();

    if (!county || !OUTCODES_URL) return;

    const res = await fetch(OUTCODES_URL + "?county=" + encodeURIComponent(county));
    if (!res.ok) return;

    const data = await res.json();
    setOptions(outcodeEl, data.outcodes || [], "Select postcode prefix", selectedOutcode);

    window.gscEditListingSync?.();
  }

  countryEl?.addEventListener("change", () => loadCounties(""));
  countyEl?.addEventListener("change", () => loadOutcodes(""));

  if (initialCountry) {
    countryEl.value = initialCountry;
    loadCounties(initialCounty);
  } else {
    setOptions(countyEl, [], "Select county");
    setOptions(outcodeEl, [], "Select postcode prefix");
  }
})();

(function () {
  const stepper = {
    s1: document.getElementById("js-stepper-1"),
    s2: document.getElementById("js-stepper-2"),
    s3: document.getElementById("js-stepper-3"),
    s4: document.getElementById("js-stepper-4"),
    s5: document.getElementById("js-stepper-5"),
    s6: document.getElementById("js-stepper-6"),
    msg: document.getElementById("js-stepper-msg"),
  };

  const cards = {
    c1: document.getElementById("js-card-1"),
    c2: document.getElementById("js-card-2"),
    c3: document.getElementById("js-card-3"),
    c4: document.getElementById("js-card-4"),
    c5: document.getElementById("js-card-5"),
    c6: document.getElementById("js-card-6"),
    msg6: document.getElementById("js-step6-msg"),
  };

  const activateBtn = document.getElementById("js-activate-btn");

  const required = {
    step1: ["#id_project_duration_days"],
    step2: ["#id_source_use", "#id_target_use"],
    step3: ["#id_funding_band", "#id_return_type", "#id_return_band", "#id_duration_days"],
    step4: ["#id_country", "#id_county", "#id_postcode_prefix"],
  };

  const imgInput = document.getElementById("id_images");
  const docInput = document.getElementById("id_documents");

  function hasValue(sel) {
    const el = document.querySelector(sel);
    if (!el) return false;
    return String(el.value || "").trim() !== "";
  }

  function stepOk(selectors) {
    return (selectors || []).every(hasValue);
  }

  function mediaSelected() {
    const imgCount = imgInput?.files?.length || 0;
    const docCount = docInput?.files?.length || 0;
    return (imgCount + docCount) > 0;
  }

  function setPill(el, ok) {
    if (!el) return;
    el.classList.remove("bg-success", "text-white", "bg-light", "text-dark", "border");
    if (ok) el.classList.add("bg-success", "text-white");
    else el.classList.add("bg-light", "text-dark", "border");
  }

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

    if (activateBtn) {
      activateBtn.disabled = !okAll;
    }
  }

  window.gscEditListingSync = sync;

  const watch = [
    ...required.step1, ...required.step2, ...required.step3, ...required.step4,
  ];

  watch.forEach(sel => {
    const el = document.querySelector(sel);
    el?.addEventListener("change", sync);
    el?.addEventListener("input", sync);
  });

  imgInput?.addEventListener("change", sync);
  docInput?.addEventListener("change", sync);

  sync();
})();

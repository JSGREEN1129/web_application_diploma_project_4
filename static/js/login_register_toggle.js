(function () {
  // Login password toggle
  const loginPw = document.getElementById("id_password_login");
  const loginBtn = document.getElementById("toggleLoginPassword");
  if (loginPw && loginBtn) {
    loginBtn.addEventListener("click", function () {
      const isPw = loginPw.getAttribute("type") === "password";
      loginPw.setAttribute("type", isPw ? "text" : "password");
      loginBtn.textContent = isPw ? "Hide" : "Show";
    });
  }

  // Register password toggles (both)
  const regPw1 = document.getElementById("id_password_register_1");
  const regPw2 = document.getElementById("id_password_register_2");
  const regBtn = document.getElementById("toggleRegisterPasswords");
  if (regPw1 && regPw2 && regBtn) {
    regBtn.addEventListener("click", function () {
      const isPw = regPw1.getAttribute("type") === "password";
      regPw1.setAttribute("type", isPw ? "text" : "password");
      regPw2.setAttribute("type", isPw ? "text" : "password");
      regBtn.textContent = isPw ? "Hide passwords" : "Show passwords";
    });
  }
})();
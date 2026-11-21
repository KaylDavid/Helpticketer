(function () {
  "use strict";

  const email = document.getElementById("email");
  const password = document.getElementById("password");
  const submit = document.querySelector('[data-testid="login-submit"]');

  // "Use" buttons in the demo box fill in the form. The password is public demo data.
  document.querySelectorAll(".demo-fill").forEach(function (button) {
    button.addEventListener("click", function () {
      if (!email || !password) {
        return;
      }
      email.value = button.dataset.email;
      password.value = button.dataset.password;
      if (submit) {
        submit.focus(); // so pressing Enter logs in
      }
    });
  });
})();
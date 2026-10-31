/* Carry a known service from a landing page into the existing request form. */
(function () {
  'use strict';
  function chooseRequestedService() {
    var requested = new URLSearchParams(window.location.search).get('service');
    var select = document.querySelector('#homeowner-request-form select[name="service_needed"]');
    if (!requested || !select || select.value) return;
    var allowed = Array.from(select.options).some(function (option) {
      return !option.disabled && option.value === requested;
    });
    if (allowed) {
      select.value = requested;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', chooseRequestedService, { once: true });
  } else {
    chooseRequestedService();
  }
}());

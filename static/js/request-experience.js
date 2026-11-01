/* Progressive enhancement: the complete form remains usable without JavaScript. */
(function () {
  'use strict';
  const form = document.getElementById('homeowner-request-form');
  if (!form || !window.fetch) return;
  const steps = Array.from(form.querySelectorAll('[data-request-step]'));
  const next = document.getElementById('request-next');
  const back = document.getElementById('request-back');
  const progress = document.getElementById('request-progress');
  const review = document.getElementById('request-review');
  const error = document.getElementById('request-error');
  const submit = document.getElementById('request-submit');
  let busy = false;
  function validStep(step) {
    return Array.from(step.querySelectorAll('input,select,textarea')).every(function (field) {
      return field.reportValidity();
    });
  }
  function show(index) {
    steps.forEach((step, n) => { step.hidden = n !== index; });
    progress.textContent = 'Step ' + (index + 1) + ' of 2 · ' + (index ? 'Contact details' : 'Property details');
    if (index) {
      review.textContent = form.elements.service_needed.value + ' · ZIP ' + form.elements.zip_code.value;
      review.hidden = false;
    }
    steps[index].querySelector('select,input').focus({preventScroll: true});
  }
  form.querySelectorAll('[data-choose-service]').forEach(function(button){
    button.hidden = false;
    button.addEventListener('click',function(){form.elements.service_needed.value=button.dataset.chooseService;form.elements.zip_code.focus();});
  });
  next.hidden = false; back.hidden = false;
  steps[1].hidden = true;
  progress.textContent = 'Step 1 of 2 · Property details';
  next.addEventListener('click', () => { if (validStep(steps[0])) show(1); });
  back.addEventListener('click', () => { if (!busy) show(0); });
  form.noValidate = true;
  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (busy) return;
    for (let i = 0; i < steps.length; i++) {
      const invalid = steps[i].querySelector(':invalid');
      if (invalid) { show(i); invalid.reportValidity(); return; }
    }
    busy = true; submit.disabled = true; back.disabled = true;
    submit.textContent = 'Submitting your request…'; error.hidden = true;
    try {
      const response = await fetch(form.action, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(Object.fromEntries(new FormData(form)))});
      const result = await response.json();
      if (!response.ok) throw new Error(result.message || 'We could not save your request. Please check your details and try again.');
      window.location.assign('/request-received');
    } catch (failure) {
      error.textContent = failure.message === 'Failed to fetch' ? 'Connection interrupted. Your request may have been received. Please avoid submitting again until your connection is restored.' : failure.message;
      error.hidden = false; error.scrollIntoView({block:'center'});
      busy = false; submit.disabled = false; back.disabled = false; submit.textContent = 'Submit my request';
    }
  });
}());

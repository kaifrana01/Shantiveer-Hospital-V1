/**
 * no_double_submit.js
 * -------------------
 * Global double-submit prevention for the entire site.
 *
 * Strategy:
 *   - Uses a single document-level "submit" listener (event delegation).
 *   - On first submit: injects a hidden `_submit_token` field with a
 *     unique per-submission UUID so the server can detect duplicates,
 *     disables the clicked submit button, shows a spinner.
 *   - On any subsequent submit of the SAME form before the page
 *     navigates away: calls e.preventDefault() immediately — nothing
 *     is sent.
 *   - 20-second safety reset re-enables the button in case of a network
 *     error or server-side validation failure that keeps the user on
 *     the same page.
 *
 * No per-template wiring needed — just include this script once in the
 * base template and every <form method="post"> is protected.
 */
(function () {
    'use strict';

    // WeakMap keyed by <form> element — value is true while a submit is in-flight
    var inFlight = typeof WeakMap !== 'undefined' ? new WeakMap() : null;

    function uuid() {
        // Simple random token — not crypto-grade but sufficient as a nonce
        return Date.now().toString(36) + Math.random().toString(36).slice(2);
    }

    function findSubmitButton(form, event) {
        // The button that was actually clicked is stored by the browser on
        // the SubmitEvent as submitter (modern browsers). Fall back to the
        // first [type=submit] button.
        if (event && event.submitter) return event.submitter;
        return form.querySelector('[type="submit"]') ||
               form.querySelector('button:not([type="button"]):not([type="reset"])');
    }

    function originalLabel(btn) {
        // Store original HTML on first call so the reset can restore it exactly.
        if (!btn._origHTML) btn._origHTML = btn.innerHTML;
        return btn._origHTML;
    }

    function disableBtn(btn) {
        originalLabel(btn);           // snapshot
        btn.disabled = true;
        btn.innerHTML =
            '<span class="spinner-border spinner-border-sm me-1" ' +
            'role="status" aria-hidden="true"></span> Saving\u2026';
    }

    function enableBtn(btn) {
        btn.disabled = false;
        if (btn._origHTML) btn.innerHTML = btn._origHTML;
    }

    function onSubmit(e) {
        var form = e.target;

        // Only intercept POST forms — GET search forms are fine to repeat
        if (!form || form.tagName !== 'FORM') return;
        var method = (form.getAttribute('method') || 'get').toLowerCase();
        if (method !== 'post') return;

        // --- Block duplicate submit ---
        if (inFlight && inFlight.get(form)) {
            e.preventDefault();
            e.stopImmediatePropagation();
            return;
        }

        // --- Mark in-flight ---
        if (inFlight) inFlight.set(form, true);

        // --- Inject a unique per-submission token so the server can dedup ---
        var existing = form.querySelector('input[name="_submit_token"]');
        if (existing) existing.parentNode.removeChild(existing);
        var tokenInput = document.createElement('input');
        tokenInput.type  = 'hidden';
        tokenInput.name  = '_submit_token';
        tokenInput.value = uuid();
        form.appendChild(tokenInput);

        // --- Disable the submit button and show spinner ---
        var btn = findSubmitButton(form, e);
        if (btn) disableBtn(btn);

        // --- Safety reset after 20 s (network error / server validation) ---
        var resetTimer = setTimeout(function () {
            if (inFlight) inFlight.set(form, false);
            if (btn) enableBtn(btn);
        }, 20000);

        // --- Re-enable immediately if the page is being unloaded (success) ---
        // This prevents the "Back" button from showing a disabled form.
        window.addEventListener('pagehide', function onHide() {
            clearTimeout(resetTimer);
            window.removeEventListener('pagehide', onHide);
        }, { once: true });
    }

    // Attach at capture phase on the document so it fires before any
    // per-form handlers and before Bootstrap validation can stop it.
    document.addEventListener('submit', onSubmit, true);

})();

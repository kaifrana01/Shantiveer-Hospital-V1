// Global HMS frontend helpers
document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
        if (!confirm(el.dataset.confirm || 'Are you sure?')) e.preventDefault();
    });
});

// Lab test checkbox -> selected table
document.querySelectorAll('.test-checkbox').forEach(cb => {
    cb.addEventListener('change', function () {
        const table = document.getElementById('selectedTestsBody');
        if (!table) return;
        const name = this.dataset.name;
        const rate = this.dataset.rate;
        if (this.checked) {
            const row = document.createElement('tr');
            row.dataset.test = name;
            row.innerHTML = `<td>${name}</td><td>${rate}</td><td><input type="number" value="1" min="1" class="form-control form-control-sm test-qty" style="width:60px"></td><td class="test-amt">${rate}</td><td><button type="button" class="btn btn-sm btn-danger remove-test">×</button></td>`;
            table.appendChild(row);
            row.querySelector('.remove-test').onclick = () => { row.remove(); this.checked = false; updateLabTotal(); };
            row.querySelector('.test-qty').oninput = updateLabTotal;
        } else {
            table.querySelector(`tr[data-test="${name}"]`)?.remove();
        }
        updateLabTotal();
    });
});

function updateLabTotal() {
    let total = 0;
    document.querySelectorAll('#selectedTestsBody tr').forEach(row => {
        const rate = parseFloat(row.cells[1].textContent) || 0;
        const qty = parseInt(row.querySelector('.test-qty')?.value) || 1;
        const amt = rate * qty;
        row.querySelector('.test-amt').textContent = amt;
        total += amt;
    });
    const totalEl = document.getElementById('labTotal');
    const dueEl = document.getElementById('labDue');
    const disc = parseFloat(document.getElementById('labDiscount')?.value) || 0;
    if (totalEl) totalEl.textContent = total;
    if (dueEl) dueEl.value = Math.max(0, total - disc);
}

/**
 * Global validation for “required text” fields.
 * Rule (per user request):
 * - Only validate fields that already have the `required` attribute.
 * - If required and text is empty/whitespace => block submit.
 */
(function () {
    function isTextLike(el) {
        if (!el || !el.tagName) return false;
        const tag = el.tagName.toLowerCase();
        const type = (el.getAttribute('type') || '').toLowerCase();

        if (tag === 'textarea') return true;
        if (tag === 'select') return true; // treat empty option as invalid when required
        if (tag === 'input') {
            // “text” meaning: text/search/email/tel/url/password/number (digit input) etc.
            // We will validate emptiness for any required input except checkbox/radio/button.
            if (['checkbox', 'radio', 'submit', 'button', 'reset', 'file', 'hidden', 'image'].includes(type)) {
                return false;
            }
            return true;
        }
        return false;
    }

    function fieldLabel(el) {
        const id = el.id;
        if (id) {
            const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
            if (label && label.textContent) return label.textContent.trim();
        }
        if (el.name) return el.name;
        return 'This field';
    }

    function valueIsEmpty(el) {
        if (el.tagName.toLowerCase() === 'select') {
            // Consider empty value as empty
            return !(el.value || '').trim();
        }
        // inputs + textarea
        return !(el.value || '').trim();
    }

    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!form || !(form.tagName && form.tagName.toLowerCase() === 'form')) return;

        const requiredFields = Array.from(form.querySelectorAll('[required]'))
            .filter(isTextLike);

        for (const el of requiredFields) {
            if (valueIsEmpty(el)) {
                const lbl = fieldLabel(el);
                // Use native alert to keep it simple across pages
                alert(`${lbl} is required. Please enter some text.`);
                try {
                    el.focus();
                    el.select && el.select();
                } catch (_) {}
                e.preventDefault();
                return;
            }
        }
    }, true);
})();


if (document.getElementById('labDiscount')) {
    document.getElementById('labDiscount').addEventListener('input', updateLabTotal);
}

/**
 * Prevent duplicate submissions: disable the submit button on the first click
 * and restore it after 6 seconds as a fallback in case the server returns an
 * error and the page does not navigate away.
 *
 * Excluded: forms with data-no-disable attribute (e.g. search/filter forms).
 */
(function () {
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!form || form.tagName.toLowerCase() !== 'form') return;
        if (form.dataset.noDisable !== undefined) return;
        // Do not disable if the required-field validation already blocked submit
        if (e.defaultPrevented) return;

        const btn = form.querySelector('[type="submit"]:not([data-no-disable])');
        if (!btn || btn.disabled) return;

        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Saving…';

        // Re-enable after 6 s so users are not permanently locked out on errors
        setTimeout(function () {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }, 6000);
    }, false);
})();


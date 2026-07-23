# TODO - Accountant Panel + Expenses/Bills/Due/Referral Filter + Income Form

## Step 1: Repo understanding (RBAC + module_access)
- [x] Read `core/rbac.py` (or RBAC implementation file used by dashboard/sidebar)
- [x] Identify how `module_access` is computed and how to gate templates/views
- [x] Identify existing groups/roles and permissions model

## Step 2: Add Accountant login panel
- [x] Add “Accountant” tile to `templates/accounts/login.html` (role picker)
- [x] Update `accounts/views.py` `_role_redirect()` to route accountant to `core:dashboard`
- [x] Add “Accountant” role + module access mapping in `core/rbac.py` (view-only where required)

## Step 3: Expenses control for IPD/OPD/Lab/Ultrasound
- [ ] Inspect `expenses/models.py` and `expenses/views.py` for existing “paid/advance” design
- [ ] Map how “bills due” are calculated today
- [ ] Add/update views/templates to update dues and show patient lists for all modules

## Step 4: Bills screen update (Due + patient lists)
- [ ] Inspect bill templates/views:
  - [ ] `templates/ipd/bill.html`
  - [ ] OPD bill template (if exists)
  - [ ] Lab billing views/templates
  - [ ] Ultrasound billing views/templates
- [ ] Implement unified “due” display and an accountant-accessible update action (or view-only)

## Step 5: Rename “mess” → “MISC”
- [ ] Find occurrences in templates/forms/models
- [ ] Update label/choices safely without breaking stored DB values

## Step 6: Referral doctor filtering across modules
- [ ] Identify field storing referral doctor in each module model
- [ ] Add filter parameter + UI on:
  - [ ] IPD patient list
  - [ ] OPD patient list
  - [ ] Lab patient list
  - [ ] Ultrasound patient list
- [ ] Ensure filtering applies both on GET and server-side queryset

## Step 7: Create Accountant income form
- [ ] Inspect `income/models.py` and `income/views.py` for existing ledger/daybook
- [ ] Extend income categories for: Ultrasound, OPD, IPD, Lab, Pharmacy, OT, Extra
- [ ] Add new accountant-only form + route
- [ ] Save entries into existing income ledger/daybook models

## Step 8: Testing
- [ ] Verify Accountant can login and is restricted to view-only actions
- [ ] Verify due + referral filter + new income form work end-to-end


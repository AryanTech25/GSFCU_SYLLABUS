/* syllabus_builder.js
   Single, self-contained IIFE for the Syllabus Builder view.
   No onclick / onchange attributes anywhere — all wiring via event delegation.
   Single DOMContentLoaded listener. Single AJAX Save Draft flow.
*/
(function () {
    'use strict';

    /* ── Constants ─────────────────────────────────────────────────────── */
    const TOTAL_STEPS = 8;
    const BLOOMS_MAP = {
        Cognitive:   ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create'],
        Affective:   ['Receiving', 'Responding', 'Valuing', 'Organizing', 'Characterizing (by a value or value complex)'],
        Psychomotor: ['Perception', 'Set', 'Guided Response', 'Mechanism', 'Complex Overt Response', 'Adaptation', 'Origination'],
    };

    let currentStep = 1;

    /* ── DOM helpers ───────────────────────────────────────────────────── */
    const $ = (sel, ctx) => (ctx || document).querySelector(sel);
    const $$ = (sel, ctx) => Array.from((ctx || document).querySelectorAll(sel));
    const getVal = name => { const el = $(`[name="${name}"]`); return el ? el.value : ''; };
    const newId = () => Date.now() + Math.floor(Math.random() * 1000);

    /* ── Toast ─────────────────────────────────────────────────────────── */
    function showToast(msg, type) {
        const el = $('#sb-toast');
        if (!el) return;
        el.textContent = msg;
        el.className = 'show ' + (type || 'success');
        clearTimeout(el._timer);
        el._timer = setTimeout(() => { el.className = ''; }, 4000);
    }

    /* ── Progress bar ──────────────────────────────────────────────────── */
    function updatePctBar(pct, isDone) {
        const fill  = $('#sb-pct-bar');
        const label = $('#sb-pct-label');
        if (!fill || !label) return;
        fill.style.width = pct + '%';
        if (isDone) {
            fill.style.background = 'linear-gradient(90deg,#16a34a,#4ade80)';
            label.style.color = '#15803d';
        } else if (pct < 40) {
            fill.style.background = 'linear-gradient(90deg,#dc2626,#f87171)';
            label.style.color = '#b91c1c';
        } else if (pct < 75) {
            fill.style.background = 'linear-gradient(90deg,#d97706,#fbbf24)';
            label.style.color = '#92400e';
        } else {
            fill.style.background = 'linear-gradient(90deg,#2563eb,#60a5fa)';
            label.style.color = '#1e40af';
        }
        label.textContent = isDone ? '✓ Complete' : (pct + '%');
    }

    /* ── Step navigation ───────────────────────────────────────────────── */
    function showStep(step) {
        $$('.step-content').forEach(el => el.classList.remove('active'));
        $$('.sb-step').forEach(el => el.classList.remove('active', 'completed'));
        const target = $(`#step${step}`);
        if (target) target.classList.add('active');
        for (let i = 1; i <= TOTAL_STEPS; i++) {
            const node = $(`.sb-step[data-step="${i}"]`);
            if (!node) continue;
            if (i < step) node.classList.add('completed');
            else if (i === step) node.classList.add('active');
        }
        currentStep = step;
        window.scrollTo(0, 0);
    }

    /* ── Calculations ──────────────────────────────────────────────────── */
    function recalcHoursCredits() {
        const sum = names => names.reduce((a, n) => a + (parseInt(getVal(n)) || 0), 0);
        const th = $('#total_hours');
        if (th) th.value = sum(['hours_lecture', 'hours_practical', 'hours_tutorial']);
        const tc = $('#total_credits');
        if (tc) tc.value = sum(['credit_lecture', 'credit_practical', 'credit_tutorial']);
    }

    function recalcEval() {
        let t = 0; $$('.eval-theory').forEach(el => t += parseInt(el.value || 0) || 0);
        const tt = $('#theory_total'); if (tt) tt.textContent = t;
        let p = 0; $$('.eval-prac').forEach(el => p += parseInt(el.value || 0) || 0);
        const pt = $('#practical_total'); if (pt) pt.textContent = p;
    }

    function recalcUnitTotal() {
        let total = 0;
        $$('.unit-weight').forEach(el => total += parseFloat(el.value || 0) || 0);
        const disp = $('#total_weightage_display');
        if (disp) { disp.textContent = total; disp.style.color = Math.abs(total - 100) < 0.1 ? 'green' : 'red'; }
    }

    function recalcPracTotal() {
        let total = 0;
        $$('.prac-weight').forEach(el => total += parseFloat(el.value || 0) || 0);
        const disp = $('#total_practical_weightage_display');
        if (disp) disp.textContent = total;
    }

    /* ── Bloom's helpers ───────────────────────────────────────────────── */
    function bloomsSubOptions(domain, selected) {
        const opts = BLOOMS_MAP[domain] || [];
        return '<option value="">-- Select Subdomain --</option>' +
            opts.map(s => `<option value="${s}"${s === selected ? ' selected' : ''}>${s}</option>`).join('');
    }

    /* ── Dynamic field builders ────────────────────────────────────────── */
    function addObjective(val, domain, subdomain) {
        val = val || ''; domain = domain || ''; subdomain = subdomain || '';
        const container = $('#objectives_container');
        if (!container) return;
        const id = newId();
        const domOpts = ['Cognitive', 'Affective', 'Psychomotor']
            .map(d => `<option value="${d}"${d === domain ? ' selected' : ''}>${d}</option>`).join('');
        const subOpts = domain ? bloomsSubOptions(domain, subdomain) : '<option value="">-- Select Subdomain --</option>';
        const div = document.createElement('div');
        div.className = 'sb-dynamic-item';
        div.innerHTML = `
<button type="button" class="sb-btn sb-btn-danger sb-remove-btn" data-action="remove-item">🗑</button>
<textarea class="sb-textarea" rows="2" name="obj_${id}" placeholder="Enter objective..." required>${val}</textarea>
<div style="display:flex;gap:10px;align-items:center;margin-top:6px;">
  <div style="flex:1;">
    <label class="sb-label" style="font-size:.8rem;">Bloom's Taxonomy Domain</label>
    <select class="sb-input" name="obj_domain_${id}" id="obj_domain_${id}" data-uid="${id}" data-action="blooms-domain" style="width:100%;">
      <option value="">-- Select Domain --</option>${domOpts}
    </select>
  </div>
  <div style="flex:1;">
    <label class="sb-label" style="font-size:.8rem;">Bloom's Taxonomy Subdomain</label>
    <select class="sb-input" name="obj_subdomain_${id}" id="obj_subdomain_${id}" style="width:100%;">${subOpts}</select>
  </div>
</div>`;
        container.appendChild(div);
    }

    function addTheoryUnit(title, description, weightage, hours) {
        title = title || ''; description = description || '';
        weightage = weightage !== undefined ? weightage : '';
        hours = hours !== undefined ? hours : '';
        const container = $('#theory_units_container');
        if (!container) return;
        const id = newId();
        const div = document.createElement('div');
        div.className = 'sb-dynamic-item';
        div.innerHTML = `
<button type="button" class="sb-btn sb-btn-danger sb-remove-btn" data-action="remove-unit">🗑 Remove Unit</button>
<div class="sb-row">
  <div class="sb-form-group" style="flex:2">
    <label class="sb-label">Unit Title</label>
    <input type="text" class="sb-input" name="unit_title_${id}" value="${title}" required>
  </div>
  <div class="sb-form-group">
    <label class="sb-label">Weight (%)</label>
    <input type="number" class="sb-input unit-weight" name="unit_weight_${id}" value="${weightage}" min="0" required>
  </div>
  <div class="sb-form-group">
    <label class="sb-label">Hours</label>
    <input type="number" class="sb-input" name="unit_hours_${id}" value="${hours}" min="0" required>
  </div>
</div>
<div class="sb-form-group">
  <label class="sb-label">Topics</label>
  <textarea class="sb-textarea" rows="3" name="unit_desc_${id}" required>${description}</textarea>
</div>`;
        container.appendChild(div);
    }

    function addPractical(description, weightage, hours) {
        description = description || '';
        weightage = weightage !== undefined ? weightage : '';
        hours = hours !== undefined ? hours : '';
        const container = $('#practicals_container');
        if (!container) return;
        const id = newId();
        const div = document.createElement('div');
        div.className = 'sb-dynamic-item';
        div.innerHTML = `
<button type="button" class="sb-btn sb-btn-danger sb-remove-btn" data-action="remove-practical">🗑 Remove</button>
<div class="sb-form-group">
  <label class="sb-label">Practical Description</label>
  <textarea class="sb-textarea" rows="2" name="prac_desc_${id}" required>${description}</textarea>
</div>
<div class="sb-row">
  <div class="sb-form-group">
    <label class="sb-label">Weight (%)</label>
    <input type="number" class="sb-input prac-weight" name="prac_weight_${id}" value="${weightage}" min="0" required>
  </div>
  <div class="sb-form-group">
    <label class="sb-label">Hours</label>
    <input type="number" class="sb-input" name="prac_hours_${id}" value="${hours}" min="0" required>
  </div>
</div>`;
        container.appendChild(div);
    }

    function addCO(description) {
        description = description || '';
        const container = $('#co_container');
        if (!container) return;
        const count = container.children.length + 1;
        const id = newId();
        const div = document.createElement('div');
        div.className = 'sb-dynamic-item co-item';
        div.setAttribute('data-co', `CO${count}`);
        div.innerHTML = `
<button type="button" class="sb-btn sb-btn-danger sb-remove-btn" data-action="remove-co">🗑</button>
<label class="sb-label">CO${count}</label>
<textarea class="sb-textarea" rows="2" name="co_desc_${id}" placeholder="Description for CO${count}" required>${description}</textarea>`;
        container.appendChild(div);
        renderMappingTable();
    }

    function reindexCOs() {
        $$('.co-item').forEach((item, idx) => {
            const num = idx + 1;
            const lbl = item.querySelector('label');
            if (lbl) lbl.textContent = `CO${num}`;
            item.setAttribute('data-co', `CO${num}`);
        });
        renderMappingTable();
    }

    function renderMappingTable() {
        const container = $('#mapping_matrix_container');
        if (!container) return;
        const saved = {};
        $$('input', container).forEach(inp => { saved[inp.name] = inp.value; });

        const coItems = $$('.co-item');
        if (coItems.length === 0) {
            container.innerHTML = '<p><em>Add COs above to generate table.</em></p>';
            return;
        }
        let html = '<table class="sb-preview-table" style="width:100%"><thead><tr><th>CO</th>';
        for (let i = 1; i <= 12; i++) html += `<th>PO${i}</th>`;
        html += '</tr></thead><tbody>';
        coItems.forEach((item, idx) => {
            const coNum = idx + 1;
            html += `<tr><td><strong>CO${coNum}</strong></td>`;
            for (let i = 1; i <= 12; i++) {
                const name = `map_co${coNum}_po${i}`;
                const val = saved[name] !== undefined ? saved[name] : '';
                html += `<td><input type="number" min="0" max="3" class="sb-input" style="padding:4px;width:40px;" name="${name}" value="${val}"></td>`;
            }
            html += '</tr>';
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    function addResource(cat, content) {
        cat = cat || ''; content = content || '';
        const container = $('#resources_container');
        if (!container) return;
        const id = newId();
        const div = document.createElement('div');
        div.className = 'sb-dynamic-item';
        div.innerHTML = `
<button type="button" class="sb-btn sb-btn-danger sb-remove-btn" data-action="remove-item">🗑 Remove</button>
<div class="sb-form-group">
  <label class="sb-label">Category</label>
  <input type="text" class="sb-input" name="res_cat_${id}" placeholder="e.g. Reference Books" value="${cat}" required>
</div>
<div class="sb-form-group">
  <label class="sb-label">Content</label>
  <textarea class="sb-textarea" rows="3" name="res_content_${id}" placeholder="Enter resource details..." required>${content}</textarea>
</div>`;
        container.appendChild(div);
    }

    /* ── Preview ───────────────────────────────────────────────────────── */
    function generatePreview() {
        const form = $('#syllabusForm');
        const p = $('#syllabusPreview');
        if (!form || !p) return;
        const previewUrl = form.dataset.previewUrl;
        if (!previewUrl) return;

        p.innerHTML = '<div style="text-align:center;padding:2rem;">Generating accurate preview...</div>';
        fetch(previewUrl, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
            .then(r => r.text())
            .then(html => {
                p.innerHTML = '';
                const iframe = document.createElement('iframe');
                iframe.style.cssText = 'width:100%;height:1150px;border:none;';
                p.appendChild(iframe);
                const doc = iframe.contentWindow || iframe.contentDocument.document || iframe.contentDocument;
                doc.document.open();
                doc.document.write(html);
                doc.document.close();
            })
            .catch(() => {
                p.innerHTML = '<div style="color:red;text-align:center;">Error generating preview. Please try again.</div>';
            });
    }

    /* ── PDF action ────────────────────────────────────────────────────── */
    function generatePdfAction() {
        const btn = $('#btn-generate-pdf');
        const url = btn ? btn.dataset.pdfUrl : '';
        if (url && url !== 'null') {
            window.location.href = url;
        } else {
            showToast('Please Save Draft first before generating PDF.', 'error');
        }
    }

    /* ── Validation ────────────────────────────────────────────────────── */
    function validateForm() {
        let firstInvalid = null;
        $$('.invalid').forEach(el => el.classList.remove('invalid'));
        $$('input[name^="map_co"]').forEach(el => { if (!el.value.trim()) el.value = 0; });

        function check(el) {
            if (!el || el.disabled || el.readOnly) return;
            let fail = !el.value.trim();
            if (!fail && el.type === 'number' && parseFloat(el.value) < 0) fail = true;
            if (fail) { el.classList.add('invalid'); if (!firstInvalid) firstInvalid = el; }
        }

        [
            'input[name^="course_code"]', 'input[name^="course_name"]',
            'select[name="category"]', 'select[name="focus"]', 'select[name="course_focus"]',
            'textarea[name="rationale"]',
            'input[name="hours_lecture"]', 'input[name="hours_practical"]', 'input[name="hours_tutorial"]',
            'input[name="credit_lecture"]', 'input[name="credit_practical"]', 'input[name="credit_tutorial"]',
            'textarea[name^="obj_"]', 'select[name^="obj_domain_"]', 'select[name^="obj_subdomain_"]',
            'input[name^="unit_title_"]', 'textarea[name^="unit_desc_"]',
            'input[name^="unit_weight_"]', 'input[name^="unit_hours_"]',
            'textarea[name^="prac_desc_"]', 'input[name^="prac_weight_"]', 'input[name^="prac_hours_"]',
            'textarea[name^="co_desc_"]', 'input[name^="map_co"]',
            'input[name^="res_cat_"]', 'textarea[name^="res_content_"]',
            'input[name^="eval_"]',
        ].forEach(sel => $$(sel).forEach(check));

        const prereq = $('input[name="prerequisites"]');
        if (prereq && prereq.value.trim().length < 3) {
            prereq.classList.add('invalid');
            if (!firstInvalid) firstInvalid = prereq;
        }

        function ensureSection(containerId, addFn, qsel) {
            const c = $(`#${containerId}`);
            if (c && c.querySelectorAll('.sb-dynamic-item').length === 0) {
                addFn(); check(c.querySelector(qsel));
            }
        }
        ensureSection('objectives_container', () => addObjective(), 'textarea[name^="obj_"]');
        ensureSection('theory_units_container', () => addTheoryUnit(), 'input[name^="unit_title"]');
        ensureSection('co_container', () => addCO(), 'textarea');

        let unitTotal = 0;
        $$('.unit-weight').forEach(el => unitTotal += parseFloat(el.value || 0) || 0);
        let customMsg = null;
        if (Math.abs(unitTotal - 100) > 0.1) {
            $$('.unit-weight').forEach(el => el.classList.add('invalid'));
            if (!firstInvalid) {
                firstInvalid = $('.unit-weight');
                customMsg = `Total Theory Unit Weight must be 100%. Current: ${unitTotal}%`;
            }
        }

        if (firstInvalid) {
            const stepContent = firstInvalid.closest('.step-content');
            if (stepContent) showStep(parseInt(stepContent.id.replace('step', '')));
            setTimeout(() => {
                firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                firstInvalid.focus();
            }, 100);
            let msg = customMsg || 'Please fill all required fields before saving.';
            if (!customMsg && firstInvalid.name === 'prerequisites') msg = 'Course prerequisite is required (min 3 chars).';
            showToast(msg, 'error');
            return false;
        }
        return true;
    }

    /* ── AJAX Save Draft ───────────────────────────────────────────────── */
    function ajaxSave() {
        const form = $('#syllabusForm');
        if (!form) return;

        $$('input[name^="map_co"]', form).forEach(el => { if (!el.value.trim()) el.value = 0; });

        const saveBtn = $('#sb-ajax-save-btn');
        const spinner = $('#sb-spinner');

        if (saveBtn) saveBtn.style.display = 'none';
        if (spinner) spinner.style.display = 'flex';

        const fd = new FormData(form);
        fd.set('save_mode', 'draft');
        fd.set('current_slide', String(currentStep));
        const lmInput = $('input[name="last_modified"]', form);
        if (lmInput) fd.set('last_modified', lmInput.value);

        fetch(form.action || window.location.href, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: fd,
        })
            .then(r => {
                if (!r.ok && r.status !== 400) throw new Error('Server error ' + r.status);
                return r.json();
            })
            .then(data => {
                if (saveBtn) saveBtn.style.display = 'flex';
                if (spinner) spinner.style.display = 'none';
                if (data.ok) {
                    showToast(data.message || 'Draft saved.', 'success');
                    updatePctBar(data.pct || 0, data.is_complete || false);
                    let lm = $('input[name="last_modified"]', form);
                    if (!lm) {
                        lm = document.createElement('input');
                        lm.type = 'hidden'; lm.name = 'last_modified';
                        form.appendChild(lm);
                    }
                    if (data.updated_at) lm.value = data.updated_at;
                    if (data.syllabus_id) {
                        const pdfBtn = $('#btn-generate-pdf');
                        if (pdfBtn) pdfBtn.dataset.pdfUrl = '/faculty/generate-pdf/' + data.syllabus_id + '/';
                    }
                } else {
                    showToast(data.error || 'Save failed.', 'error');
                }
            })
            .catch(err => {
                if (saveBtn) saveBtn.style.display = 'flex';
                if (spinner) spinner.style.display = 'none';
                showToast('Save failed: ' + err.message, 'error');
            });
    }

    /* ── Hydration ─────────────────────────────────────────────────────── */
    function hydrate(data) {
        if (data.objectives && data.objectives.length > 0) {
            data.objectives.forEach(o => addObjective(o.text, o.domain, o.subdomain));
        } else { addObjective(''); }

        if (data.units && data.units.length > 0) {
            data.units.forEach(u => addTheoryUnit(u.title, u.description, u.weightage, u.hours));
        } else { addTheoryUnit(); }

        if (data.practicals && data.practicals.length > 0) {
            data.practicals.forEach(p => addPractical(p.description, p.weightage, p.hours));
        } else { addPractical(); }

        if (data.outcomes && data.outcomes.length > 0) {
            data.outcomes.forEach(co => addCO(co.description));
            data.outcomes.forEach((co, idx) => {
                const mapping = co.mapping || {};
                ['po1','po2','po3','po4','po5','po6','po7','po8','po9','po10','po11','po12'].forEach(po => {
                    const inp = $(`input[name="map_co${idx + 1}_${po}"]`);
                    if (inp) inp.value = mapping[po] !== undefined ? mapping[po] : 0;
                });
            });
        } else { addCO(); }

        if (data.resources && data.resources.length > 0) {
            data.resources.forEach(r => addResource(r.category, r.content));
        } else { addResource('Reference Books', ''); }

        setTimeout(() => { recalcHoursCredits(); recalcEval(); recalcUnitTotal(); recalcPracTotal(); }, 50);
    }

    function defaultInit() {
        addObjective('Understand the core aim of the course.');
        addTheoryUnit();
        addPractical();
        addCO();
        addResource('Reference Books', '');
    }

    /* ── Event delegation ──────────────────────────────────────────────── */
    function setupDelegation() {
        document.addEventListener('click', e => {
            const t = e.target;

            const navNext = t.closest('[data-step-next]');
            if (navNext) { e.preventDefault(); showStep(+navNext.dataset.stepNext); return; }

            const navPrev = t.closest('[data-step-prev]');
            if (navPrev) { e.preventDefault(); showStep(+navPrev.dataset.stepPrev); return; }

            if (t.closest('[data-action="preview"]')) { e.preventDefault(); generatePreview(); showStep(8); return; }
            if (t.closest('[data-action="ajax-save"]')) { e.preventDefault(); ajaxSave(); return; }
            if (t.closest('[data-action="generate-pdf"]')) { e.preventDefault(); generatePdfAction(); return; }
            if (t.closest('[data-action="add-objective"]')) { e.preventDefault(); addObjective(); return; }
            if (t.closest('[data-action="add-unit"]')) { e.preventDefault(); addTheoryUnit(); return; }
            if (t.closest('[data-action="add-practical"]')) { e.preventDefault(); addPractical(); return; }
            if (t.closest('[data-action="add-co"]')) { e.preventDefault(); addCO(); return; }
            if (t.closest('[data-action="add-resource"]')) { e.preventDefault(); addResource(); return; }

            const rmItem = t.closest('[data-action="remove-item"]');
            if (rmItem) { e.preventDefault(); rmItem.closest('.sb-dynamic-item').remove(); return; }

            const rmUnit = t.closest('[data-action="remove-unit"]');
            if (rmUnit) { e.preventDefault(); rmUnit.closest('.sb-dynamic-item').remove(); recalcUnitTotal(); return; }

            const rmPrac = t.closest('[data-action="remove-practical"]');
            if (rmPrac) { e.preventDefault(); rmPrac.closest('.sb-dynamic-item').remove(); recalcPracTotal(); return; }

            const rmCO = t.closest('[data-action="remove-co"]');
            if (rmCO) { e.preventDefault(); rmCO.closest('.sb-dynamic-item').remove(); reindexCOs(); return; }
        });

        document.addEventListener('input', e => {
            const t = e.target;
            if (t.matches('.calc-hours, .calc-credits')) recalcHoursCredits();
            if (t.matches('.eval-theory, .eval-prac')) recalcEval();
            if (t.matches('.unit-weight')) recalcUnitTotal();
            if (t.matches('.prac-weight')) recalcPracTotal();
        });

        document.addEventListener('change', e => {
            if (e.target.matches('[data-action="blooms-domain"]')) {
                const sel = e.target;
                const subSel = $(`#obj_subdomain_${sel.dataset.uid}`);
                if (subSel) subSel.innerHTML = bloomsSubOptions(sel.value, '');
            }
        });
    }

    /* ── Focus invalid field from Django context ───────────────────────── */
    function focusInvalidField() {
        const meta = $('#sb-invalid-field');
        if (!meta || !meta.content) return;
        const el = $(`[name="${meta.content}"]`);
        if (!el) return;
        const stepContent = el.closest('.step-content');
        if (stepContent) showStep(parseInt(stepContent.id.replace('step', '')));
        setTimeout(() => {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.focus();
            el.classList.add('invalid');
            showToast('Validation Error: Please correct the highlighted field.', 'error');
        }, 300);
    }

    /* ── Boot ──────────────────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', () => {
        setupDelegation();

        let draftData = null;
        try {
            const dataEl = $('#draft-data');
            if (dataEl) {
                const raw = dataEl.textContent;
                if (raw && raw !== 'null') draftData = JSON.parse(raw);
            }
        } catch (e) {
            console.error('Draft data parse error', e);
        }

        if (draftData && typeof draftData === 'object') {
            hydrate(draftData);
        } else {
            defaultInit();
        }

        focusInvalidField();
    });
}());

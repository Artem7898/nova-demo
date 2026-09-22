'use strict';
(() => {
  const gettext = window.gettext || (message => message);
  const format = (message, values) => message.replace(/\{(\w+)\}/g, (_, key) => String(values[key]));
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const csrf = () => $('[name=csrfmiddlewaretoken]')?.value || '';
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
  $('.language-switcher')?.addEventListener('submit', e => { e.currentTarget.elements.next.value = location.pathname + location.search + location.hash; });
  let toastTimer;
  function toast(message) { const node = $('#toast'); node.textContent = message; node.classList.add('visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove('visible'), 4500); }
  async function request(url, options = {}) {
    const response = await fetch(url, {...options, headers: {'X-CSRFToken': csrf(), 'Content-Type':'application/json', ...options.headers}});
    const type = response.headers.get('content-type') || '';
    const data = type.includes('application/json') ? await response.json() : {detail: format(gettext('HTTP {status}: сервер вернул неожиданный ответ.'), {status: response.status})};
    if (!response.ok) { const error = new Error(data.detail || JSON.stringify(data, null, 2)); error.data = data; throw error; }
    return data;
  }
  async function copy(value) { try { await navigator.clipboard.writeText(value); toast(gettext('Скопировано')); } catch { toast(gettext('Браузер не разрешил копирование. Выделите текст вручную.')); } }
  $('.mobile-menu')?.addEventListener('click', e => { const open = $('#sidebar').classList.toggle('open'); e.currentTarget.setAttribute('aria-expanded', String(open)); });
  document.addEventListener('click', e => { if (window.innerWidth <= 700 && !e.target.closest('.sidebar, .mobile-menu')) { $('#sidebar').classList.remove('open'); $('.mobile-menu')?.setAttribute('aria-expanded','false'); } });
  let health;
  async function loadHealth() {
    try { health = await request('/lab/api/health/'); renderHealth(); return health; }
    catch (e) { if ($('#remote-status')) $('#remote-status').textContent = gettext('Нет ответа'); toast(e.message); }
  }
  function renderHealth() {
    const remote = ['redis','memcached'].filter(n => health.services[n].status === 'ready').length;
    if ($('#remote-status')) $('#remote-status').innerHTML = `${remote} / 2 <small>${remote ? gettext('подключены') : gettext('не подключены')}</small>`;
    if ($('#service-grid')) $('#service-grid').innerHTML = Object.entries(health.services).map(([id, service]) => {
      const ready = service.status === 'ready'; const label = ready ? gettext('Подключено') : service.status === 'not_configured' ? gettext('Не настроено') : gettext('Недоступно');
      return `<article class="service-card">${icon(id === 'memory' ? 'bolt' : 'db')}<h3>${escape(service.label)}</h3><span class="status-chip ${ready ? 'success' : 'warning'}">${label}</span><p>${id === 'memory' ? gettext('В пределах процесса') : id === 'database' ? gettext('Основная база демо') : gettext('Реальная интеграционная проверка')}</p></article>`;
    }).join('');
  }
  $('#refresh-health')?.addEventListener('click', loadHealth);
  if (['lab','integrations'].includes(document.body.dataset.page)) loadHealth();
  if ($('#scenario-data')) {
    const scenarios = JSON.parse($('#scenario-data').textContent);
    const results = new Map(); let busy = false; let group = 'all';
    let selected = scenarios.find(s => s.id === new URLSearchParams(location.search).get('scenario')) || scenarios[0];
    const labels = {passed:gettext('Пройдено'), failed:gettext('Ошибка'), skipped:gettext('Не выполнено'), running:gettext('Выполняется')};
    const classes = {passed:'success', failed:'failed', skipped:'warning', running:'running'};
    const icons = {basics:'shield',performance:'bolt',consistency:'db',execution:'code',adapters:'box',observability:'grid',infrastructure:'plug'};
    function list() {
      const term = $('#scenario-search').value.toLowerCase();
      const filtered = scenarios.filter(s => `${s.title} ${s.group} ${s.description}`.toLowerCase().includes(term) && (group === 'all' || group === s.group_id || group === 'more' && !['basics','performance'].includes(s.group_id)));
      $('#scenario-list').innerHTML = filtered.length ? filtered.map(s => `<button class="scenario-card ${s.id===selected.id ? 'selected' : ''}" data-scenario="${s.id}" aria-pressed="${s.id===selected.id}"><span class="scenario-icon">${icon(icons[s.group_id] || 'code')}</span><span><span class="scenario-title">${escape(s.title)}</span><span class="scenario-subtitle">${escape(s.group)}${s.mode==='experimental' ? gettext(' · Эксперимент') : s.mode==='preview' ? ' · Preview' : s.requirement ? gettext(' · Нужен сервис') : ' · Live'}</span></span>${results.has(s.id) ? `<span class="card-check">${results.get(s.id).status==='passed' ? '✓' : results.get(s.id).status==='skipped' ? '—' : '!'}</span>` : icon('arrow').replace('<svg ', '<svg class="card-arrow" ')}</button>`).join('') : `<p class="no-results">${escape(gettext('Сценарии не найдены. Попробуйте другой запрос.'))}</p>`;
      $$('[data-scenario]').forEach(button => button.addEventListener('click', () => { if (!busy) select(scenarios.find(s => s.id===button.dataset.scenario)); }));
    }
    function tab(name) { $$('.output-tab').forEach(n => {n.classList.toggle('active',n.dataset.tab===name);n.setAttribute('aria-selected',String(n.dataset.tab===name));}); ['result','code','json'].forEach(t => $(`#${t}-panel`).hidden = t!==name); }
    $$('.output-tab').forEach(n => n.addEventListener('click', () => tab(n.dataset.tab)));
    function select(s) {
      selected = s; $('#experiment-title').textContent = s.title; $('#experiment-group').textContent = s.group.toUpperCase();
      $('#experiment-description').textContent = s.description; $('#payload').value = JSON.stringify(s.payload, null, 2);
      $('#payload').readOnly = !['validation','planner'].includes(s.id);
      $('#preset-actions').hidden = s.id!=='validation';
      $('#input-hint').textContent = ['validation','planner'].includes(s.id) ? gettext('Редактируйте JSON. Произвольный Python-код не принимается.') : gettext('У сценария фиксированные входные данные для воспроизводимой проверки.');
      $('#code-output').textContent = s.code.replaceAll('\\n','\n');
      history.replaceState(null,'',`/?scenario=${encodeURIComponent(s.id)}`);
      showResult(results.get(s.id)); list();
    }
    function showResult(result) {
      const status = $('#experiment-status'); status.className = `status-chip ${result ? classes[result.status] : 'neutral'}`; status.textContent = result ? labels[result.status] : gettext('Не запущен');
      $('#check-count').textContent = result?.checks.length ? result.checks.length : '';
      $('#run-time').textContent = result ? `${result.duration_ms.toFixed(1)} ms` : '—';
      $('#json-output').textContent = result ? JSON.stringify(result, null, 2) : gettext('// Запустите сценарий, чтобы получить ответ.');
      if (!result) { $('#result-panel').innerHTML = `<div class="empty-output"><span class="terminal-glyph">&gt;_</span><strong>${escape(gettext('Всё готово к первому запуску'))}</strong><p>${escape(gettext('Здесь появятся проверки, SQL-счётчики'))}<br>${escape(gettext('и фактический ответ Django Nova.'))}</p></div>`; return; }
      const sql = result.steps.reduce((s,x) => s+x.sql_count,0);
      $('#result-panel').innerHTML = `<div class="result-summary"><span>${escape(gettext('Время запуска'))}<strong>${result.duration_ms.toFixed(1)} <small>ms</small></strong></span><span>${escape(gettext('SQL в шагах'))}<strong>${sql}</strong></span><span>${escape(gettext('Проверки'))}<strong>${result.checks.filter(c=>c.passed).length}/${result.checks.length}</strong></span></div>` +
        result.checks.map(c=>`<div class="check-line ${c.passed?'':'fail'}"><span class="check-symbol">${c.passed?'✓':'×'}</span><span>${escape(c.label)}</span></div>`).join('') +
        (result.output.message ? `<div class="result-message">${escape(result.output.message)}</div>` : '') +
        (result.steps.length ? `<div class="step-list">${result.steps.map(s=>`<div class="step-line"><span>${escape(s.label)}</span><strong>${s.sql_count} SQL · ${s.duration_ms.toFixed(2)} ms</strong></div>`).join('')}</div>` : '') +
        (result.output.outcome ? `<div class="result-outcome">${result.output.outcome==='accepted' ? gettext('ACCEPTED · Модель прошла валидацию') : gettext('REJECTED · Невалидная запись заблокирована')}</div>` : '') +
        (result.output.sql_note ? `<div class="result-outcome">${escape(result.output.sql_note)}</div>` : '') +
        (selected.mode!=='live' ? `<div class="result-outcome">${escape(gettext('Preview / эксперимент. Подробные границы — во вкладке JSON.'))}</div>` : '');
    }
    function updateHistory() {
      $('#session-history').hidden = results.size===0; $('#export-results').disabled = results.size===0;
      const passed = [...results.values()].filter(r=>r.status==='passed').length;
      $('#session-pass').innerHTML = `${passed} / ${results.size} <small>${escape(gettext('сценариев пройдено'))}</small>`;
      $('#history-body').innerHTML = [...results.entries()].map(([id,r])=>`<tr><td>${escape(scenarios.find(s=>s.id===id).title)}</td><td><span class="status-chip ${classes[r.status]}">${labels[r.status]}</span></td><td>${r.checks.filter(c=>c.passed).length}/${r.checks.length}</td><td>${r.duration_ms.toFixed(1)} ms</td></tr>`).join('');
    }
    function setBusy(value) { busy=value; $('#run-scenario').disabled=value; $('#run-all').disabled=value; $('#payload').disabled=value; $('#run-scenario span').textContent=value?gettext('Выполняется…'):gettext('Запустить сценарий'); }
    async function execute(s,payload) {
      $('#experiment-status').className='status-chip running'; $('#experiment-status').textContent=gettext('Выполняется');
      const controller = new AbortController(); const timer = setTimeout(()=>controller.abort(),45000);
      try {const r=await request(`/lab/api/run/${s.id}/`, {method:'POST', body:JSON.stringify(payload), signal:controller.signal}); results.set(s.id,r);if (selected.id===s.id) showResult(r);updateHistory();list();return r;}
      catch(e){showResult(results.get(s.id)); throw new Error(e.name==='AbortError'?gettext('Сервер не ответил за 45 секунд. Запуск мог продолжиться; проверьте журнал.'):e.message);}
      finally{clearTimeout(timer);}
    }
    async function runCurrent() { if(busy)return; let payload;try{payload=JSON.parse($('#payload').value);if(!payload || Array.isArray(payload)||typeof payload!=='object')throw new Error();}catch{toast(gettext('Введите корректный JSON-объект.'));return;}setBusy(true);tab('result');try{await execute(selected,payload);}catch(e){toast(e.message);}finally{setBusy(false);} }
    $('#run-scenario').addEventListener('click',runCurrent);
    $('#run-all').addEventListener('click',async()=>{if(busy)return;setBusy(true);tab('result');let count=0;try{for(const s of scenarios){select(s);$('#run-all').innerHTML=`${icon('refresh')} ${escape(format(gettext('Проверка {current} / {total}'), {current: ++count, total: scenarios.length}))}`;await execute(s,s.payload);}}catch(e){toast(e.message);}finally{setBusy(false);$('#run-all').innerHTML=`${icon('play')} ${escape(gettext('Запустить все проверки'))}`;toast(gettext('Результаты запусков доступны ниже и в JSON.'));}});
    $('#valid-preset').addEventListener('click',()=>{$('#payload').value=JSON.stringify({name:'Studio Headphones',price:'129.00'},null,2);});
    $('#invalid-preset').addEventListener('click',()=>{$('#payload').value=JSON.stringify({name:'Studio Headphones',price:'-10.00'},null,2);});
    $('#scenario-search').addEventListener('input',list);
    $$('.filter').forEach(n=>n.addEventListener('click',()=>{group=n.dataset.group;$$('.filter').forEach(t=>t.classList.toggle('active',t===n));list();}));
    $('.copy-output').addEventListener('click',()=>{const active=$('.output-tab.active').dataset.tab;copy(active==='code'?$('#code-output').textContent:JSON.stringify(results.get(selected.id)||{},null,2));});
    $('#export-results').addEventListener('click',()=>{const blob=new Blob([JSON.stringify({nova_version:health?.version,exported_at:new Date().toISOString(),results:[...results.values()]},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='nova-demo-results.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
    document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();runCurrent();}if(e.key==='/'&&!e.target.matches('input,textarea')){e.preventDefault();$('#scenario-search').focus();}});
    select(selected);
  }
  if ($('#product-dialog')) {
    const dialog=$('#product-dialog');const form=$('#product-form');
    function errors(data){$('#form-errors').textContent=typeof data==='string'?data:JSON.stringify(data,null,2);$('#form-errors').hidden=false;}
    function open(product) {form.reset();$('#form-errors').hidden=true;form.elements.id.value=product?.id||'';$('#dialog-title').textContent=product?gettext('Изменить товар'):gettext('Новый товар');$('#delete-product').hidden=!product;if(product){form.elements.name.value=product.name;form.elements.price.value=product.price;form.elements.category.value=product.category;form.elements.is_active.checked=product.is_active;}dialog.showModal();}
    $('#new-product').addEventListener('click',()=>open());$$('.close-dialog').forEach(n=>n.addEventListener('click',()=>dialog.close()));
    $$('.edit-product').forEach(n=>n.addEventListener('click',async()=>{try{open(await request(`/api/products/${n.dataset.id}/`));}catch(e){toast(e.message);}}));
    form.addEventListener('submit',async e=>{e.preventDefault();const id=form.elements.id.value;const button=$('[type=submit]',form);button.disabled=true;$('#form-errors').hidden=true;try{await request(`/api/products/${id?`${id}/`:''}`,{method:id?'PATCH':'POST',body:JSON.stringify({name:form.elements.name.value,price:form.elements.price.value,category:Number(form.elements.category.value),is_active:form.elements.is_active.checked})});location.reload();}catch(error){errors(error.data||error.message);}finally{button.disabled=false;}});
    $('#delete-product').addEventListener('click',async e=>{if(!confirm(gettext('Удалить этот товар из вашей песочницы?')))return;e.currentTarget.disabled=true;try{await request(`/api/products/${form.elements.id.value}/`,{method:'DELETE'});location.reload();}catch(error){errors(error.data||error.message);e.currentTarget.disabled=false;}});
  }
  if ($('#schema-model')) {
    async function loadSchema(){try{const result=await request(`/lab/api/schema/${$('#schema-model').value}/`);$('#schema-json').textContent=JSON.stringify(result.schema,null,2);$('#model-fields').innerHTML=result.fields.map(f=>`<div class="field-row"><strong>${escape(f.name)}${f.primary_key?' · PK':''}</strong><span>${escape(f.type)}${f.nullable?' ?':''}</span></div>`).join('');}catch(e){$('#schema-json').textContent=e.message;}}
    $('#schema-model').addEventListener('change',loadSchema);$('#copy-schema').addEventListener('click',()=>copy($('#schema-json').textContent));loadSchema();
  }
})();

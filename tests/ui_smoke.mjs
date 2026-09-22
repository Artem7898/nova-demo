import {spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM, VirtualConsole} from 'jsdom';

const rendered = spawnSync('uv', ['run', '--locked', 'python', 'tests/render_ui_fixtures.py'], {encoding:'utf8',maxBuffer:4*1024*1024});
assert.equal(rendered.status,0,rendered.stderr);
const fixtures = JSON.parse(rendered.stdout);
const script = readFileSync('static/demo/app.js','utf8');
const tick = () => new Promise(resolve=>setTimeout(resolve,5));
function boot(path, language='ru') {
  const localized = fixtures[language];
  const errors=[]; const calls=[]; const virtualConsole=new VirtualConsole();
  virtualConsole.on('jsdomError', e=>errors.push(e));
  const dom=new JSDOM(localized.pages[path],{url:`http://localhost${path}`,runScripts:'outside-only',virtualConsole});
  const w=dom.window;
  w.fetch=async(url,opts={})=>{
    calls.push({url,...opts});
    const data=localized.api[url] || {id:999,name:'Created',price:'29.00'};
    return {ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>data};
  };
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  w.HTMLDialogElement.prototype.close=function(){this.open=false;};
  w.eval(localized.catalog);
  w.eval(script);
  return {dom,w,d:w.document,errors,calls};
}

test('lab renders 19 scenarios, sends CSRF, and displays real validation and cache results',async()=>{
  const {dom,d,errors,calls}=boot('/');
  try {
    assert.equal(d.querySelectorAll('[data-scenario]').length,19);
    d.querySelector('#run-scenario').click(); await tick();
    assert.equal(d.querySelector('#experiment-status').textContent,'Пройдено');
    assert.match(d.querySelector('#result-panel').textContent,/ACCEPTED/);
    assert.ok(calls.find(c=>c.method==='POST').headers['X-CSRFToken']);
    assert.equal(d.querySelector('#run-scenario').disabled,false);
    d.querySelector('[data-scenario=cache]').click();
    d.querySelector('#run-scenario').click();await tick();
    assert.match(d.querySelector('#result-panel').textContent,/0 SQL/);
    d.querySelector('[data-tab=json]').click();
    assert.equal(d.querySelector('#json-panel').hidden,false);
    assert.equal(d.querySelector('#result-panel').hidden,true);
    assert.equal(d.querySelector('#history-body').children.length,2);
    assert.equal(d.querySelector('#export-results').disabled,false);
    assert.deepEqual(errors,[]);
  } finally {dom.window.close();}
});

test('search, invalid JSON and presets work without submitting invalid input',async()=>{
  const {dom,d,w,calls,errors}=boot('/');
  try {
    d.querySelector('#invalid-preset').click();
    assert.equal(JSON.parse(d.querySelector('#payload').value).price,'-10.00');
    d.querySelector('#payload').value='invalid';
    d.querySelector('#run-scenario').click();await tick();
    assert.equal(calls.filter(c=>c.method==='POST').length,0);
    assert.match(d.querySelector('#toast').textContent,/JSON/);
    d.querySelector('#scenario-search').value='no such scenario';
    d.querySelector('#scenario-search').dispatchEvent(new w.Event('input'));
    assert.equal(d.querySelectorAll('[data-scenario]').length,0);
    assert.deepEqual(errors,[]);
  } finally {dom.window.close();}
});

test('catalog modal opens and validation errors remain visible',async()=>{
  const {dom,d,w,errors}=boot('/catalog/');
  try {
    assert.equal(d.querySelectorAll('.product-card').length,8);
    d.querySelector('#new-product').click();
    assert.equal(d.querySelector('dialog').open,true);
    const form=d.querySelector('#product-form');
    form.elements.name.value='New item';form.elements.price.value='-1';
    w.fetch=async()=>({ok:false,status:400,headers:{get:()=> 'application/json'},json:async()=>({price:['Must be positive']})});
    form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();
    assert.equal(d.querySelector('#form-errors').hidden,false);
    assert.match(d.querySelector('#form-errors').textContent,/Must be positive/);
    assert.equal(form.querySelector('[type=submit]').disabled,false);
    d.querySelector('.close-dialog').click();assert.equal(d.querySelector('dialog').open,false);
    assert.deepEqual(errors,[]);
  } finally {dom.window.close();}
});

test('schema switch and service status render API data',async()=>{
  for (const path of ['/schemas/','/integrations/']) {
    const {dom,d,w,errors}=boot(path);
    try {
      await tick();
      if(path==='/schemas/'){
        assert.ok(d.querySelectorAll('.field-row').length>0);
        d.querySelector('#schema-model').value='category';
        d.querySelector('#schema-model').dispatchEvent(new w.Event('change'));await tick();
        assert.match(d.querySelector('#schema-json').textContent,/slug/);
      } else assert.equal(d.querySelectorAll('.service-card').length,4);
      assert.deepEqual(errors,[]);
    } finally {dom.window.close();}
  }
});


test('English lab uses translated filters, validation, results and current-location language form',async()=>{
  const {dom,d,w,errors}=boot('/', 'en');
  try {
    assert.equal(d.documentElement.lang,'en');
    assert.equal(d.querySelector('.language-switcher [value=en]').getAttribute('aria-pressed'),'true');
    assert.equal(d.querySelector('#run-scenario span').textContent,'Run scenario');
    d.querySelector('[data-group=performance]').click();
    assert.ok(d.querySelectorAll('[data-scenario]').length>0);
    assert.ok(d.querySelectorAll('[data-scenario]').length<19);
    d.querySelector('[data-scenario=cache]').click();
    d.querySelector('#run-scenario').click();await tick();
    assert.equal(d.querySelector('#experiment-status').textContent,'Passed');
    assert.match(d.querySelector('#result-panel').textContent,/The repeated read executes no SQL/);
    assert.doesNotMatch(d.querySelector('#result-panel').textContent,/[А-Яа-яЁё]/);
    const form=d.querySelector('.language-switcher');
    form.addEventListener('submit',e=>e.preventDefault());
    form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
    assert.equal(form.elements.next.value,w.location.pathname+w.location.search+w.location.hash);
    assert.match(form.elements.next.value,/cache/);
    d.querySelector('[data-group=all]').click();
    d.querySelector('[data-scenario=validation]').click();
    d.querySelector('#payload').value='broken JSON';
    d.querySelector('#run-scenario').click();await tick();
    assert.equal(d.querySelector('#toast').textContent,'Enter a valid JSON object.');
    d.querySelector('#scenario-search').value='no matching scenario';
    d.querySelector('#scenario-search').dispatchEvent(new w.Event('input'));
    assert.equal(d.querySelector('.no-results').textContent,'No scenarios found. Try a different search.');
    assert.deepEqual(errors,[]);
  } finally {dom.window.close();}
});

test('English catalog, schema and service UI use the real Django JavaScript catalog',async()=>{
  for(const path of ['/catalog/','/schemas/','/integrations/']){
    const {dom,d,errors}=boot(path,'en');
    try{
      await tick();
      assert.equal(d.documentElement.lang,'en');
      if(path==='/catalog/'){
        d.querySelector('#new-product').click();
        assert.equal(d.querySelector('#dialog-title').textContent,'New product');
        assert.match(d.querySelector('dialog').textContent,/Save product/);
      }else if(path==='/schemas/'){
        assert.ok(d.querySelectorAll('.field-row').length>0);
      }else{
        assert.equal(d.querySelectorAll('.service-card').length,4);
        assert.match(d.querySelector('#service-grid').textContent,/Connected/);
      }
      assert.deepEqual(errors,[]);
    }finally{dom.window.close();}
  }
});

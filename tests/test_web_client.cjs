const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function loadClient() {
  function element() {
    return {
      children: [], style: {}, dataset: {}, value: '',
      classList: { add() {}, remove() {} },
      appendChild(child) { this.children.push(child); },
      set innerHTML(value) {
        assert.equal(value, '', 'Only clearing markup is allowed');
        this.children = [];
      },
    };
  }
  const elements = new Map();
  const alerts = [];
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    createElement: element,
  };
  const context = vm.createContext({
    document, window: { addEventListener() {} },
    alert: message => alerts.push(message),
    setTimeout: () => 1, clearTimeout() {},
    setInterval: () => 1, clearInterval() {},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../interface/web_client/app.js'), 'utf8'), context);
  return { context, document, alerts };
}

test('filenames render as literal text and checkbox data', () => {
  const { context, document } = loadClient();
  const name = '<img src=x onerror=alert(1)>.csv';
  context.filename = name;
  vm.runInContext('ALL_FILES = [{name: filename, matches_pattern: false}]; renderFileList();', context);
  const row = document.getElementById('files-tbody').children[0];
  assert.equal(row.children[1].textContent, name);
  assert.equal(row.children[0].children[0].dataset.name, name);
});

test('request failure restores controls and reports error', async () => {
  const { context, document, alerts } = loadClient();
  await vm.runInContext("TOKEN = 'test'; runAction(async () => { showActivity('Loading'); throw new Error('offline'); });", context);
  assert.equal(document.getElementById('refresh-btn').disabled, false);
  assert.equal(alerts[0], 'Operation failed: offline');
});

test('cleanup keeps disconnected controls disabled', async () => {
  const { context, document } = loadClient();
  await vm.runInContext('runAction(async () => {});', context);
  assert.equal(document.getElementById('refresh-btn').disabled, true);
});

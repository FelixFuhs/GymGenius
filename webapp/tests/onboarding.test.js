const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { JSDOM } = require('jsdom');

test('QuickStart sets flag and hides modal', () => {
  const code = fs.readFileSync(path.resolve(__dirname, '../js/onboarding.js'), 'utf8');
  const dom = new JSDOM(`<!DOCTYPE html><div id="onboarding-modal"><button id="qs-start-btn"></button></div>`);

  global.window = dom.window;
  global.document = dom.window.document;
  global.localStorage = dom.window.localStorage;

  const context = { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage };
  vm.createContext(context);
  vm.runInContext(code, context);

  context.QuickStart.checkFirstTime();
  const modal = dom.window.document.getElementById('onboarding-modal');
  expect(modal.classList.contains('show')).toBe(true);

  dom.window.document.getElementById('qs-start-btn').dispatchEvent(new dom.window.Event('click'));

  expect(context.localStorage.getItem('gg_first_time')).toBe('no');
  expect(modal.classList.contains('show')).toBe(false);
});

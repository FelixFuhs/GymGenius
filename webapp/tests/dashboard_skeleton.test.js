const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { JSDOM } = require('jsdom');

// Verify skeleton loaders render before fetch resolves

test('skeleton appears during 1RM fetch', () => {
  const code = fs.readFileSync(path.resolve(__dirname, '../js/dashboard_charts.js'), 'utf8');

  const dom = new JSDOM(`<!DOCTYPE html>
    <div id="chart1RMStatus"></div>
    <div class="chart-container"><canvas id="1rmEvolutionChart"></canvas></div>`,
    { url: 'http://localhost/dashboard.html' });

  global.window = dom.window;
  global.document = dom.window.document;
  global.localStorage = { getItem: () => 'user1' };
  global.navigator = dom.window.navigator;

  const context = {
    window: dom.window,
    document: dom.window.document,
    localStorage: global.localStorage,
    navigator: dom.window.navigator,
    console,
    fetch: jest.fn(() => new Promise(() => {}))
  };

  vm.createContext(context);
  vm.runInContext(code, context);

  context.fetchAndRender1RMEvolutionData('1');

  expect(dom.window.document.querySelector('.chart-skeleton')).not.toBeNull();
});

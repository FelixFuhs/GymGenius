const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { JSDOM } = require('jsdom');

test('tooltip title updates after fetching recommendation', async () => {
  const code = fs.readFileSync(path.resolve(__dirname, '../js/app.js'), 'utf8');

  const dom = new JSDOM(`<!DOCTYPE html><div id="app-root"></div><footer><nav></nav></footer>`, {
    url: 'http://localhost/#logset?exerciseId=1&exerciseName=Bench'
  });

  global.window = dom.window;
  global.document = dom.window.document;
  global.localStorage = dom.window.localStorage;
  global.navigator = dom.window.navigator;

  const context = {
    window: dom.window,
    document: dom.window.document,
    localStorage: dom.window.localStorage,
    navigator: dom.window.navigator,
    console,
    fetch: jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        recommended_weight_kg: 100,
        target_reps_low: 5,
        target_reps_high: 8,
        target_rir: 2,
        explanation: 'the reason'
      })
    })
  };

  vm.createContext(context);
  vm.runInContext(code, context);

  context.currentUserId = 'user1';

  const page = context.LogSetPage();
  await context.fetch.mock.results[0].value;
  await new Promise(setImmediate);

  expect(page.querySelector('#rec-tooltip-trigger').title).toBe('the reason');
});

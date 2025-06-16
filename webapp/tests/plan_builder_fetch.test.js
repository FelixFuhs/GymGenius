const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { JSDOM } = require('jsdom');

test('plan builder fetches exercises with auth header', async () => {
  const appCode = fs.readFileSync(path.resolve(__dirname, '../js/app.js'), 'utf8');
  const pbCode = fs.readFileSync(path.resolve(__dirname, '../js/plan_builder.js'), 'utf8');

  const dom = new JSDOM(`<!DOCTYPE html>
    <ul id="exercise-list"></ul>
    <div id="drop-zone"></div>
    <ul id="volume-list"></ul>
    <ul id="frequency-list"></ul>
    <button id="save-plan"></button>
    <button id="load-plan"></button>
    <button id="clear-plan"></button>
    <ul id="plan-templates-list"></ul>`, { url: 'http://localhost/plan_builder.html' });

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
    fetch: jest.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) })
  };

  vm.createContext(context);
  vm.runInContext(appCode, context);
  context.storeToken('tok');
  vm.runInContext(pbCode, context);

  dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));

  await context.fetch.mock.results[0].value;
  expect(context.fetch).toHaveBeenCalled();
  expect(context.fetch.mock.calls[0][0]).toContain('/v1/exercises');
  expect(context.fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer tok');
});

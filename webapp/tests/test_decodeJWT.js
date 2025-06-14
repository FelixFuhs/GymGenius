const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const code = fs.readFileSync(require('path').resolve(__dirname, '../js/app.js'), 'utf8');
const context = {};
vm.createContext(context);
vm.runInContext(code, context);

const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
const payloadObj = { sub: '123' };
const payload = Buffer.from(JSON.stringify(payloadObj)).toString('base64url');
const token = `${header}.${payload}.signature`;

const decoded = context.decodeJWT(token);
assert.deepStrictEqual(decoded.sub, '123');
console.log('decodeJWT test passed');

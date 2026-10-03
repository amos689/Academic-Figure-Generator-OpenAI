import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import { displayDate, elapsed, parseServerDate } from '../src/lib/workbench.ts';

const naive = '2026-10-03T11:20:30';
const utc = '2026-10-03T11:20:30.000Z';

test('server dates default to UTC and preserve explicit timezone instants', () => {
  for (const value of [naive, `${naive}Z`, `${naive}+00:00`, '2026-10-03T21:20:30+10:00', '2026-10-03T07:20:30-04:00', '2026-10-03T16:50:30+0530']) {
    assert.equal(parseServerDate(value)?.toISOString(), utc, value);
  }
  assert.equal(parseServerDate('2026-10-03T11:20:30+10:00')?.toISOString(), '2026-10-03T01:20:30.000Z');
  assert.equal(parseServerDate('2026-10-03T11:20:30.123456')?.toISOString(), '2026-10-03T11:20:30.123Z');
  assert.equal(parseServerDate('2026-10-03 11:20:30.1')?.toISOString(), '2026-10-03T11:20:30.100Z');
  assert.equal(parseServerDate('2026-10-03')?.toISOString(), '2026-10-03T00:00:00.000Z');
  assert.equal(parseServerDate('2024-02-29T00:00:00')?.toISOString(), '2024-02-29T00:00:00.000Z');
});

test('invalid or missing server dates are safe and never normalized into another day', () => {
  for (const value of [undefined, null, '', ' ', 'not a date', '2026-02-29T00:00:00', '2026-02-30T11:20:30', '2026-13-03T11:20:30', '2026-10-03T24:00:00', '2026-10-03T11:20:60', '2026-10-03T11:20:30+24:00', '2026-10-03T11:20:30Z+10:00']) {
    assert.equal(parseServerDate(value), null, String(value));
    assert.equal(displayDate(value, 'en'), '-');
    assert.equal(displayDate(value, 'zh'), '-');
    assert.equal(elapsed(value, `${naive}Z`), '-');
  }
  assert.equal(elapsed(naive, 'invalid finish'), '-');
  assert.equal(elapsed(naive, ''), '-');
});

test('elapsed time handles running jobs and mixed naive/aware boundaries', t => {
  t.mock.method(Date, 'now', () => Date.UTC(2026, 9, 3, 11, 22, 0));
  assert.equal(elapsed(naive), '1m 30s');
  assert.equal(elapsed(naive, null), '1m 30s');
  assert.equal(elapsed(naive, '2026-10-03T11:22:00'), '1m 30s');
  assert.equal(elapsed(naive, '2026-10-03T21:22:00+10:00'), '1m 30s');
  assert.equal(elapsed('2026-10-03T07:20:30-04:00', '2026-10-03T11:20:59'), '29s');
  assert.equal(elapsed('2026-10-03T11:23:00'), '0s');
});

test('parsing, elapsed time, and bilingual display are independent of the machine timezone', () => {
  const moduleUrl = new URL('../src/lib/workbench.ts', import.meta.url).href;
  const script = `
    import { parseServerDate, elapsed, displayDate } from ${JSON.stringify(moduleUrl)};
    Date.now = () => Date.UTC(2026, 9, 3, 11, 22, 0);
    console.log(JSON.stringify({
      parsed: parseServerDate(${JSON.stringify(naive)}).toISOString(),
      running: elapsed(${JSON.stringify(naive)}),
      completed: elapsed(${JSON.stringify(naive)}, '2026-10-03T21:22:00+10:00'),
      en: displayDate(${JSON.stringify(naive)}, 'en'),
      zh: displayDate(${JSON.stringify(naive)}, 'zh'),
      dst: displayDate('2026-10-03T16:30:00', 'en'),
      invalid: displayDate('2026-02-30T11:20:30', 'en'),
    }));
  `;
  for (const timezone of ['UTC', 'Australia/Sydney', 'America/New_York']) {
    const output = execFileSync(process.execPath, ['--experimental-strip-types', '--input-type=module', '-e', script], {
      encoding: 'utf8', env: { ...process.env, TZ: timezone }, timeout: 10000,
    });
    const actual = JSON.parse(output);
    const format = (value, locale) => new Date(value).toLocaleString(locale, { timeZone: timezone, dateStyle: 'medium', timeStyle: 'short' });
    assert.deepEqual(actual, {
      parsed: utc, running: '1m 30s', completed: '1m 30s',
      en: format(utc, 'en-GB'), zh: format(utc, 'zh-CN'),
      dst: format('2026-10-03T16:30:00Z', 'en-GB'), invalid: '-',
    }, timezone);
  }
});

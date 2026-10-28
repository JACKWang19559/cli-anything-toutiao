// Pure Node tests of the shipped driver; these never start a browser.
import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeHot, normalizeLinks, run } from '../utils/browser_driver.mjs';

const ID = '7701568905705308681';
const ID2 = '7701568905705308682';
const article = `https://www.toutiao.com/article/${ID}/`;
const article2 = `https://www.toutiao.com/article/${ID2}/`;
const trending = `https://www.toutiao.com/trending/${ID}/`;
const hotRow = (url = trending, title = ' 测试热榜 ') => ({
  Url: url, Title: title, HotValue: '123456789', Label: '热',
});
const jump = url => `https://so.toutiao.com/search/jump?url=${encodeURIComponent(url)}`;

test('hot results preserve 19-digit identifiers as exact strings', () => {
  const items = normalizeHot({data: [hotRow()]}, 20);
  assert.deepEqual(items, [{id: ID, kind: 'trending', url: trending,
    rank: 1, title: '测试热榜', heat: '123456789', label: '热'}]);
});

test('hot results cap valid entries and rank after dropping invalid links', () => {
  const items = normalizeHot({data: [hotRow('https://example.com/'), hotRow(), hotRow(article2)]}, 1);
  assert.equal(items.length, 1);
  assert.equal(items[0].id, ID);
  assert.equal(items[0].rank, 1);
});

test('hot payload shape errors are explicit', () => {
  for (const payload of [null, undefined, [], {}, {data: null}, {data: {}}]) {
    assert.throws(() => normalizeHot(payload, 5), {code: 'site_changed'});
  }
  assert.throws(() => normalizeHot({data: []}, 5), {code: 'empty_response'});
});

test('malformed hot rows are skipped without masking subsequent valid rows', () => {
  const items = normalizeHot({data: [null, 12, 'text', {}, {Url: article, Title: 4}, hotRow()]}, 10);
  assert.equal(items.length, 1);
  assert.equal(items[0].id, ID);
  assert.throws(() => normalizeHot({data: [null, {}]}, 10), {code: 'empty_response'});
});

test('direct article aliases deduplicate without rounding identifiers', () => {
  const items = normalizeLinks([
    {href: article, title: ' 第一篇 ', author: '作者', summary: '摘要'},
    {href: `https://m.toutiao.com/a${ID}/?source=x`, title: '重复'},
    {href: `https://www.toutiao.com/i${ID2}/`, title: '第二篇'},
  ], 10, true);
  assert.deepEqual(items, [
    {id: ID, kind: 'article', url: article, title: '第一篇', author: '作者', summary: '摘要'},
    {id: ID2, kind: 'article', url: article2, title: '第二篇', author: null, summary: null},
  ]);
});

test('ordinary and nested search jump links resolve to the source article', () => {
  for (const href of [jump(article), jump(jump(article)), jump(jump(jump(article)))]) {
    assert.equal(normalizeLinks([{href, title: '搜索结果'}], 5, true)[0]?.url, article);
  }
});

test('double percent encoded search targets resolve without losing IDs', () => {
  const href = jump(encodeURIComponent(article));
  const items = normalizeLinks([{href, title: '双重编码搜索结果'}], 5, true);
  assert.equal(items.length, 1);
  assert.equal(items[0].id, ID);
  assert.equal(items[0].url, article);
});

test('invalid, external and excessively nested jumps cannot become articles', () => {
  let deep = article;
  for (let index = 0; index < 12; index++) deep = jump(deep);
  const items = normalizeLinks([
    {href: jump('https://example.com/article/' + ID), title: '外站'},
    {href: 'https://so.toutiao.com/search/jump', title: '缺少目标'},
    {href: jump('%E0%A4%A'), title: '无效编码'},
    {href: deep, title: '过深跳转'},
  ], 20, true);
  assert.deepEqual(items, []);
});

test('article-only normalization filters raw nonarticle and unrelated links', () => {
  // DOM scoping is performed by extractSearch. This helper cannot know where a
  // valid article link appeared, so this test only checks raw-link semantics.
  const rows = [
    {href: '/', title: '首页导航'},
    {href: 'https://example.com/', title: '无关链接'},
    {href: trending, title: '热榜专题'},
    {href: `https://www.toutiao.com/video/${ID2}/`, title: '视频'},
    {href: article, title: '文章结果'},
  ];
  const items = normalizeLinks(rows, 10, true);
  assert.deepEqual(items.map(item => item.url), [article]);
});

test('feed normalization retains content kinds and caps the actual list', () => {
  const items = normalizeLinks([
    {href: article, title: '文章'},
    {href: `https://www.toutiao.com/video/${ID2}/`, title: '视频'},
  ], 10);
  assert.deepEqual(items.map(item => item.kind), ['article', 'video']);
  assert.equal(normalizeLinks([{href: article, title: '文章'}, {href: article2, title: '第二篇'}], 1).length, 1);
  assert.deepEqual(normalizeLinks([], 50), []);
});

test('malformed link rows and nontext titles do not crash normalization', () => {
  const items = normalizeLinks([
    null, 7, {}, {href: article, title: 23}, {href: article, title: '  '},
    {href: article, title: '有效文章'},
  ], 10, true);
  assert.equal(items.length, 1);
  assert.equal(items[0].title, '有效文章');
});

async function fakeRun(request, options = {}) {
  const events = [], messages = [];
  const previousTaskSpace = globalThis.taskSpace;
  const previousLog = console.log;
  const page = {
    async goto(url) { events.push(['goto', url]); },
    async fetch(path) {
      events.push(['fetch', path]);
      if (options.fetchError) throw options.fetchError;
      return {ok: true, body: JSON.stringify({data: [hotRow()]})};
    },
  };
  globalThis.taskSpace = async space => {
    events.push(['taskSpace', space]);
    return {
      spaceId: space,
      page(name) { events.push(['page', name]); return page; },
      async finish(value) { events.push(['finish', value]); },
      async handOff() { events.push(['handOff']); },
    };
  };
  console.log = message => messages.push(message);
  try {
    await run({operation: 'hot', args: {limit: 5}, timeout_ms: 1000,
      space: 'offline-test', managed_space: true, ...request});
  } finally {
    console.log = previousLog;
    if (previousTaskSpace === undefined) delete globalThis.taskSpace;
    else globalThis.taskSpace = previousTaskSpace;
  }
  assert.equal(messages.length, 1);
  assert.ok(messages[0].startsWith('__TOUTIAO_RESULT__'));
  return {events, result: JSON.parse(messages[0].slice('__TOUTIAO_RESULT__'.length))};
}

test('successful default read finishes its managed task space', async () => {
  const actual = await fakeRun({});
  assert.equal(actual.result.ok, true);
  assert.equal(actual.result.data.items[0].id, ID);
  assert.equal(actual.result.data.backend, 'ego-browser');
  assert.ok(Number.isFinite(Date.parse(actual.result.data.fetched_at)));
  assert.deepEqual(actual.events.filter(event => event[0] === 'finish'), [['finish', {keep: []}]]);
  assert.equal(actual.events.some(event => event[0] === 'handOff'), false);
});

test('successful read never finishes a caller-owned shared task space', async () => {
  const actual = await fakeRun({managed_space: false, space: 10});
  assert.equal(actual.result.ok, true);
  assert.deepEqual(actual.events[0], ['taskSpace', 10]);
  assert.equal(actual.events.some(event => event[0] === 'finish'), false);
  assert.equal(actual.events.some(event => event[0] === 'handOff'), false);
});

for (const operation of ['auth_login', 'creator_open']) {
  test(`${operation} hands off the page without claiming login or publication`, async () => {
    const actual = await fakeRun({operation, args: {}});
    assert.equal(actual.result.ok, true);
    assert.equal(actual.result.data.opened, true);
    assert.equal(actual.result.data.space_id, 'offline-test');
    assert.equal(actual.result.data.logged_in, undefined);
    assert.equal(actual.result.data.published, undefined);
    assert.deepEqual(actual.events.filter(event => event[0] === 'handOff'), [['handOff']]);
    assert.equal(actual.events.some(event => event[0] === 'finish'), false);
    assert.equal(actual.events.some(event => event[0] === 'fetch'), false);
  });
}

test('loss of task control returns one error without retry or finish', async () => {
  const actual = await fakeRun({}, {fetchError: new Error('EGO_TASK_SPACE_INACTIVE private account detail')});
  assert.equal(actual.result.ok, false);
  assert.equal(actual.result.error.code, 'browser_control_required');
  assert.equal(actual.result.error.message.includes('private account detail'), false);
  assert.equal(actual.events.filter(event => event[0] === 'fetch').length, 1);
  assert.equal(actual.events.some(event => event[0] === 'finish'), false);
});

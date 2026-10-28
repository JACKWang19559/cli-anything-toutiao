// Real-page adapter for ego-browser 2.1.0. No cookies leave the browser.
const MARKER = '__TOUTIAO_RESULT__';
const HOME = 'https://www.toutiao.com/';
const CHANNELS = {recommend:'推荐', tech:'科技', finance:'财经', hot:'热点', world:'国际'};

function fail(code, message) { const e = new Error(message); e.code = code; throw e; }
function result(data) { console.log(MARKER + JSON.stringify({ok:true,data})); }
function canonical(raw) {
  try {
    let url = new URL(raw, HOME);
    for(let i=0;i<4 && ['sou.toutiao.com','so.toutiao.com'].includes(url.hostname) && url.pathname === '/search/jump';i++) {
      let next=url.searchParams.get('url'); if(!next) return null;
      for(let j=0;j<3 && !/^https?:\/\//.test(next);j++) next=decodeURIComponent(next);
      url=new URL(next);
    }
    if(!['www.toutiao.com','toutiao.com','m.toutiao.com'].includes(url.hostname)) return null;
    const m = url.pathname.match(/^\/(article\/|a|i|trending\/|w\/|video\/)(\d+)\/?$/);
    if(!m) return null;
    const kind = ['article/','a','i'].includes(m[1])?'article':m[1].replace('/','');
    return {id:m[2],kind,url:`https://www.toutiao.com/${kind}/${m[2]}/`};
  } catch { return null; }
}

export function normalizeHot(payload, limit) {
  if (!payload || !Array.isArray(payload.data)) fail('site_changed','热榜数据格式已变化，或站点暂时未返回榜单。');
  const items=[];
  for(const row of payload.data) {
    if(!row || typeof row!=='object') continue;
    const link=canonical(row.Url);
    if(!link || typeof row.Title !== 'string' || !row.Title.trim()) continue;
    items.push({...link,rank:items.length+1,title:row.Title.trim(),heat:String(row.HotValue??''),label:row.Label||''});
    if(items.length>=limit) break;
  }
  if(!items.length) fail('empty_response','热榜未返回有效条目，请稍后重试。');
  return items;
}

export function normalizeLinks(rows, limit, onlyArticles=false) {
  const items=[], seen=new Set();
  for(const row of rows) {
    if(!row || typeof row!=='object') continue;
    const link=canonical(row.href), title=typeof row.title==='string'?row.title.trim():'';
    if(!link || !title || seen.has(link.id) || (onlyArticles && link.kind!=='article')) continue;
    seen.add(link.id); items.push({...link,title,author:row.author||null,summary:row.summary||null});
    if(items.length>=limit) break;
  }
  return items;
}

async function pageFailure(page, fallback='页面未返回可读取内容，请确认文章仍可访问，或稍后重试。') {
  const state=await page.evaluate(()=>({title:document.title,text:(document.body?.innerText||'').slice(0,5000)}));
  if(/安全验证|请完成验证|访问过于频繁|验证后继续|验证码/.test(state.title+'\n'+state.text))
    fail('verification_required','站点要求人工验证。请在 Ego Lite 中完成验证后重试。');
  if(/内容已删除|文章已删除|内容不存在|页面不存在|该内容已下架/.test(state.text))
    fail('article_unavailable','文章已删除、下架或不可访问。');
  fail('site_changed',fallback);
}

async function ready(page, predicate, argument, timeout) {
  try { await page.waitForFunction(predicate,argument,{timeout}); }
  catch (e) {
    // User takeover/ownership errors must stop immediately, never be retried.
    if(/control|ownership|inactive|unassigned|EGO_TASK/i.test(String(e))) throw e;
    await pageFailure(page);
  }
}

async function extractFeed(page) {
  return await page.evaluate(()=>[...document.querySelectorAll('[role="main"] a[href], main a[href]')]
    .filter(a=>a.innerText.trim().length>3 && !a.href.includes('#comment'))
    .map(a=>({href:a.href,title:a.innerText.trim(),author:a.closest('.feed-card-wrapper')?.querySelector('.feed-card-footer-cmp-author')?.innerText?.trim()||null})));
}

async function extractSearch(page) {
  // .text-xl scopes title links, excluding navigation and the unrelated hot board.
  return await page.evaluate(()=>[...document.querySelectorAll('.text-xl a[href]')]
    .map(a=>({href:a.href,title:a.innerText.trim()})));
}

async function readOperation(page, request) {
  const {operation,args}=request;
  const wait=Math.min(request.timeout_ms,25000);
  if(operation==='article') {
    await page.goto(args.url);
    await ready(page,()=>document.querySelector('article')?.innerText.trim() ||
      (document.querySelector('h1') && document.querySelector('video')) ||
      /内容已删除|内容不存在/.test(document.body?.innerText||''),undefined,wait);
    const data=await page.evaluate(()=>{
      const content=document.querySelector('article');
      const container=document.querySelector('.article-content');
      const text=content?.innerText?.trim()||'';
      const images=[...content?.querySelectorAll('img')||[]].map(img=>({url:img.getAttribute('data-src')||img.src,alt:img.alt||''})).filter(x=>/^https?:\/\//.test(x.url));
      const blocks=[];
      const escape=t=>t.replace(/([\\`*_{}\[\]<>])/g,'\\$1');
      if(content) for(const node of content.children) {
        if(node.tagName==='IMG') {
          const src=node.getAttribute('data-src')||node.src;
          if(/^https?:\/\//.test(src)) blocks.push(`![${escape(node.alt||'文章图片')}](${src.replace(/\(/g,'%28').replace(/\)/g,'%29')})`);
        } else {
          const value=(node.innerText||'').trim();
          if(value) blocks.push((/^H[1-6]$/.test(node.tagName)?'#'.repeat(Number(node.tagName[1]))+' ':'')+escape(value));
        }
      }
      return {title:document.querySelector('h1')?.innerText?.trim()||'',author:container?.querySelector('.article-meta .name')?.innerText?.trim()||null,
        published_at:container?.querySelector('.article-meta span')?.innerText?.trim()||null,
        text,markdown:blocks.join('\n\n'),images,has_video:!!document.querySelector('video'),url:location.href};
    });
    if(!data.title || !data.text) {
      if(data.has_video) fail('unsupported_content','该链接是视频内容，没有可导出的文章正文。请从搜索或频道列表选择图文文章。');
      await pageFailure(page);
    }
    return {...data,url:args.url,id:args.url.match(/\d+/)[0],kind:'article'};
  }
  if(operation==='search') {
    const params=new URLSearchParams({dvpf:'pc',source:'input',keyword:args.query,enable_druid_v2:'1',pd:'information'});
    await page.goto('https://so.toutiao.com/search?'+params);
    await ready(page,()=>document.querySelector('.text-xl a[href]') || /暂无搜索结果|未找到相关结果|没有找到相关结果/.test(document.body?.innerText||''),undefined,wait);
    const items=normalizeLinks(await extractSearch(page),args.limit,true);
    if(!items.length) {
      const empty=await page.evaluate(()=>/暂无搜索结果|未找到相关结果|没有找到相关结果/.test(document.body?.innerText||''));
      if(!empty) await pageFailure(page,'搜索页面结构变化，未找到有效的头条文章结果。');
    }
    return {query:args.query,items,count:items.length,requested_limit:args.limit,scope:'loaded_page',source:await page.url()};
  }
  await page.goto(HOME);
  if(operation==='hot') {
    const response=await page.fetch('/hot-event/hot-board/?origin=toutiao_pc',{timeout:Math.min(wait,15000)});
    if(!response.ok) fail('http_error',`热榜请求失败（HTTP ${response.status}）。请稍后重试。`);
    let payload;
    try {payload=typeof response.body==='string'?JSON.parse(response.body):response.body;}
    catch {await pageFailure(page,'热榜接口返回了非 JSON 内容，请在浏览器中检查是否要求验证。');}
    const items=normalizeHot(payload,args.limit);
    return {items,count:items.length,requested_limit:args.limit,source:HOME+'hot-event/hot-board/?origin=toutiao_pc'};
  }
  if(operation==='auth_status') {
    await ready(page,()=>document.querySelector('[aria-label="登录信息"]'),undefined,wait);
    return await page.evaluate(()=>{
      const box=document.querySelector('[aria-label="登录信息"]'),profile=box?.querySelector('a.user-info');
      const isLoginPrompt=/登录/.test(box?.innerText||'');
      return {logged_in:profile?true:isLoginPrompt?false:null,display_name:profile?.innerText?.trim()||null,source:location.origin,
        message:profile?'已检测到网页登录状态。':isLoginPrompt?'尚未登录，可运行 auth login。':'页面未明确显示登录状态。'};
    });
  }
  if(operation==='feed') {
    const channel=args.channel||'recommend', label=CHANNELS[channel]+'频道';
    await ready(page,label=>document.querySelector(`[aria-label="${label}"]`),label,wait);
    const before=JSON.stringify(await extractFeed(page));
    const selected=await page.evaluate(label=>document.querySelector(`[aria-label="${label}"]`)?.getAttribute('aria-pressed')==='true',label);
    if(!selected) {
      await page.click(`loc=role:button[name="${label}"]`);
      await ready(page,label=>document.querySelector(`[aria-label="${label}"]`)?.getAttribute('aria-pressed')==='true',label,wait);
      await ready(page,before=>JSON.stringify([...document.querySelectorAll('[role="main"] a[href], main a[href]')].filter(a=>a.innerText.trim().length>3&&!a.href.includes('#comment')).map(a=>({href:a.href,title:a.innerText.trim(),author:a.closest('.feed-card-wrapper')?.querySelector('.feed-card-footer-cmp-author')?.innerText?.trim()||null})))!==before,before,wait);
    }
    await ready(page,()=>[...document.querySelectorAll('[role="main"] a[href],main a[href]')].some(a=>/\/(article|w|video)\/\d+/.test(a.href)&&a.innerText.trim().length>3),undefined,wait);
    const items=normalizeLinks(await extractFeed(page),args.limit);
    if(!items.length) await pageFailure(page,'频道页面未返回可读取的条目。');
    return {channel,items,count:items.length,requested_limit:args.limit,scope:'loaded_page',source:HOME};
  }
  fail('unsupported_operation','不支持该浏览器操作。');
}

export async function run(request) {
  try {
    const task=await taskSpace(request.space);
    const page=task.page('p1');
    if(['auth_login','creator_open'].includes(request.operation)) {
      const url=request.operation==='auth_login'?HOME:'https://mp.toutiao.com/profile_v4/graphic/publish?from=toutiao_pc';
      await page.goto(url);
      await task.handOff();
      result({opened:true,url,space_id:task.spaceId,message:request.operation==='auth_login'?'请在浏览器中完成登录，之后运行 auth status 检查。':'已打开头条号编辑页；本命令没有填写、保存或发布内容。'});
      return;
    }
    const data=await readOperation(page,request);
    data.backend='ego-browser';data.fetched_at=new Date().toISOString();
    if(request.managed_space) await task.finish({keep:[]});
    result(data);
  } catch(e) {
    let code=e.code||'browser_failed',message='浏览器操作失败，请检查 Ego Lite 中的页面后重试。';
    if(['site_changed','verification_required','article_unavailable','unsupported_content','empty_response','http_error','unsupported_operation'].includes(code)) message=e.message;
    else if(/control|ownership|inactive|unassigned|EGO_TASK/i.test(String(e))) {code='browser_control_required';message='浏览器任务空间已由用户接管或不可用，请在 Ego Lite 中检查控制权。';}
    else if(/timed out|timeout/i.test(String(e))) {code='browser_timeout';message='网页加载超时，请检查网络或增大 --timeout。';}
    console.log(MARKER+JSON.stringify({ok:false,error:{code,message}}));
  }
}

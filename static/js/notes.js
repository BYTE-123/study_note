/* 个人笔记 · 我的文章列表
 * 职责：状态筛选（全部/草稿/已发布）+ 关键词搜索 + 分页；URL query 与筛选器双向同步。
 * 安全：标题与摘要一律经 escapeHtml 转义后再拼接。
 */
(function () {
  'use strict';

  var EMPTY_TEXT = '还没有笔记，点击「新建文章」开始记录吧';
  var VALID_STATUS = ['all', 'draft', 'published'];

  var listEl = document.getElementById('note-list');
  var form = document.getElementById('filter-form');
  var keywordInput = document.getElementById('keyword');
  var paginationEl = document.getElementById('pagination');
  var pageInfoEl = document.getElementById('page-info');
  var prevBtn = document.getElementById('prev-page');
  var nextBtn = document.getElementById('next-page');
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.filter-tab'));

  var state = { status: 'all', keyword: '', page: 1, pageSize: 10, total: 0 };

  function statusTag(status) {
    var published = status === 'published';
    return '<span class="tag' + (published ? ' tag-published' : '') + '">'
      + (published ? '已发布' : '草稿') + '</span>';
  }

  /* ---------- URL query ⇄ 筛选器 ---------- */

  function readQuery() {
    var params = new URLSearchParams(window.location.search);
    var status = params.get('status');
    state.status = VALID_STATUS.indexOf(status) >= 0 ? status : 'all';
    state.keyword = params.get('keyword') || '';
    var page = parseInt(params.get('page'), 10);
    state.page = page > 0 ? page : 1;

    keywordInput.value = state.keyword;
    syncTabs();
  }

  function writeQuery() {
    var params = new URLSearchParams();
    if (state.status !== 'all') {
      params.set('status', state.status);
    }
    if (state.keyword) {
      params.set('keyword', state.keyword);
    }
    if (state.page > 1) {
      params.set('page', String(state.page));
    }
    var query = params.toString();
    window.history.replaceState(null, '', window.location.pathname + (query ? '?' + query : ''));
  }

  function syncTabs() {
    tabs.forEach(function (tab) {
      tab.classList.toggle('is-active', tab.getAttribute('data-status') === state.status);
    });
  }

  /* ---------- 渲染 ---------- */

  function render(items) {
    if (!items || !items.length) {
      listEl.innerHTML = '<p class="empty-state">' + EMPTY_TEXT + '</p>';
      return;
    }
    listEl.textContent = '';
    items.forEach(function (item) {
      var article = document.createElement('article');
      article.className = 'note-item';

      var summary = item.summary
        ? '<p class="note-item__summary">' + window.escapeHtml(item.summary) + '</p>' : '';
      var tags = item.tags
        ? '<span class="note-item__tags">' + window.escapeHtml(item.tags) + '</span>' : '';

      article.innerHTML =
        '<div class="note-item__head">'
        + '<a class="note-item__title" href="/note?id=' + encodeURIComponent(item.id) + '">'
        + window.escapeHtml(item.title) + '</a>'
        + statusTag(item.status)
        + '</div>'
        + summary
        + '<div class="note-item__meta">' + tags
        + '<span class="note-item__time">'
        + window.escapeHtml(window.formatDateTime(item.updated_at))
        + '</span></div>';

      listEl.appendChild(article);
    });
  }

  function renderPagination() {
    var totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
    paginationEl.hidden = totalPages <= 1;
    pageInfoEl.textContent = '第 ' + state.page + ' / ' + totalPages + ' 页';
    prevBtn.disabled = state.page <= 1;
    nextBtn.disabled = state.page >= totalPages;
  }

  function renderError() {
    listEl.textContent = '';
    var block = document.createElement('div');
    block.className = 'state-block';

    var text = document.createElement('p');
    text.textContent = '加载失败，请稍后重试';

    var retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'btn btn-sm';
    retry.textContent = '重试';
    retry.addEventListener('click', load);

    block.appendChild(text);
    block.appendChild(retry);
    listEl.appendChild(block);
    paginationEl.hidden = true;
  }

  function gotoLogin() {
    window.location.href = '/login?next=' + encodeURIComponent(
      window.location.pathname + window.location.search);
  }

  /* ---------- 数据 ---------- */

  function load() {
    listEl.innerHTML = '<p class="state-block">加载中…</p>';

    var params = new URLSearchParams();
    params.set('status', state.status);
    if (state.keyword) {
      params.set('keyword', state.keyword);
    }
    params.set('page', String(state.page));

    window.api.get('/api/notes?' + params.toString()).then(function (data) {
      state.total = data.total;
      state.pageSize = data.page_size || state.pageSize;
      state.page = data.page || state.page;
      render(data.items);
      renderPagination();
      writeQuery();
    }).catch(function (error) {
      if (error && error.status === 401) {
        gotoLogin();
        return;
      }
      renderError();
    });
  }

  /* ---------- 交互 ---------- */

  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      state.status = tab.getAttribute('data-status');
      state.page = 1;
      syncTabs();
      load();
    });
  });

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    state.keyword = keywordInput.value.trim();
    state.page = 1;
    load();
  });

  prevBtn.addEventListener('click', function () {
    if (state.page > 1) {
      state.page -= 1;
      load();
    }
  });

  nextBtn.addEventListener('click', function () {
    state.page += 1;
    load();
  });

  window.initNav({ withLogout: true }).then(function (user) {
    if (!user) {
      gotoLogin();
      return;
    }
    readQuery();
    load();
  });
})();

/* 个人笔记 · 工作台
 * 职责：并发拉取统计与最近文章、渲染三张统计卡与列表、失败可重试。
 * 登录态：nav.js 渲染导航；未登录直接跳登录页。
 */
(function () {
  'use strict';

  var EMPTY_TEXT = '还没有笔记，点击「新建文章」开始记录吧';
  var recentList = document.getElementById('recent-list');

  function statusTag(status) {
    var published = status === 'published';
    return '<span class="tag' + (published ? ' tag-published' : '') + '">'
      + (published ? '已发布' : '草稿') + '</span>';
  }

  function renderStats(data) {
    ['draft', 'published', 'favorite'].forEach(function (key) {
      var card = document.querySelector('[data-stat="' + key + '"]');
      if (!card) {
        return;
      }
      card.classList.remove('skeleton');
      card.querySelector('.stat-card__value').textContent =
        String(data && data[key] != null ? data[key] : 0);
    });
  }

  function renderRecent(items) {
    if (!items || !items.length) {
      recentList.innerHTML = '<p class="empty-state">' + EMPTY_TEXT + '</p>';
      return;
    }
    recentList.textContent = '';
    items.forEach(function (item) {
      var link = document.createElement('a');
      link.className = 'recent-item';
      link.href = '/note?id=' + encodeURIComponent(item.id);
      link.innerHTML =
        '<span class="recent-item__title">' + window.escapeHtml(item.title) + '</span>'
        + '<span class="recent-item__meta">' + statusTag(item.status)
        + '<span class="recent-item__time">' + window.escapeHtml(window.formatDateTime(item.updated_at))
        + '</span></span>';
      recentList.appendChild(link);
    });
  }

  function renderError() {
    recentList.textContent = '';
    var block = document.createElement('div');
    block.className = 'state-block';

    var text = document.createElement('p');
    text.textContent = '加载失败，请稍后重试';

    var retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'btn btn-sm';
    retry.textContent = '重试';
    retry.addEventListener('click', loadAll);

    block.appendChild(text);
    block.appendChild(retry);
    recentList.appendChild(block);
  }

  function gotoLogin() {
    window.location.href = '/login?next=' + encodeURIComponent(
      window.location.pathname + window.location.search);
  }

  function loadAll() {
    recentList.innerHTML = '<p class="state-block">加载中…</p>';
    Promise.all([
      window.api.get('/api/notes/stats'),
      window.api.get('/api/notes/recent?limit=5')
    ]).then(function (result) {
      renderStats(result[0]);
      renderRecent(result[1]);
    }).catch(function (error) {
      if (error && error.status === 401) {
        gotoLogin();
        return;
      }
      renderError();
    });
  }

  window.initNav({ withLogout: true }).then(function (user) {
    if (!user) {
      gotoLogin();
      return;
    }
    loadAll();
  });
})();

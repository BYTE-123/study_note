/* 个人笔记 · 公开分享页
 * 职责：从 ?token= 拉取元信息 → 需要密码则先校验 → 渲染正文；
 *       未登录点收藏/评论跳登录；错误态（无效链接/已关闭/密码错误）可重试。
 * 依赖：api.js 提供的 window.api / renderMarkdown / formatDateTime / escapeHtml。
 */
(function () {
  'use strict';

  var STR = {
    invalid: '链接无效',
    missing: '资源不存在或分享已关闭',
    failed: '加载失败，请稍后重试',
    wrongPassword: '分享密码错误'
  };

  var token = new URLSearchParams(window.location.search).get('token');
  var currentUser = null;

  var navEl = document.getElementById('share-nav');
  var stateEl = document.getElementById('share-state');
  var gateEl = document.getElementById('share-gate');
  var gateInput = document.getElementById('share-password-input');
  var gateBtn = document.getElementById('share-view-btn');
  var gateError = document.getElementById('share-error');
  var contentEl = document.getElementById('share-content');
  var titleEl = document.getElementById('share-title');
  var metaEl = document.getElementById('share-meta');
  var bodyEl = document.getElementById('share-body-md');
  var favoriteBtn = document.getElementById('favorite-btn');
  var commentsEl = document.getElementById('share-comments');

  function loginUrl() {
    return '/login?next=' + encodeURIComponent(window.location.pathname + window.location.search);
  }

  /* ---------- 顶部精简导航 ---------- */

  function navLink(label, href) {
    var a = document.createElement('a');
    a.textContent = label;
    a.href = href;
    return a;
  }

  function renderNav() {
    fetch('/api/auth/me', { credentials: 'include' })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (payload) {
        currentUser = payload && payload.code === 'OK' ? payload.data : null;
      })
      .catch(function () { currentUser = null; })
      .then(function () {
        navEl.textContent = '';
        if (currentUser) {
          var name = document.createElement('span');
          name.className = 'share-nav__user';
          name.textContent = currentUser.username;
          navEl.appendChild(name);

          var out = document.createElement('button');
          out.type = 'button';
          out.className = 'btn btn-ghost btn-sm';
          out.textContent = '退出';
          out.addEventListener('click', function () {
            out.disabled = true;
            window.api.post('/api/auth/logout').then(function () {
              window.location.reload();
            }).catch(function () { out.disabled = false; });
          });
          navEl.appendChild(out);
        } else {
          navEl.appendChild(navLink('登录', loginUrl()));
          navEl.appendChild(navLink('注册', '/register'));
        }
      });
  }

  /* ---------- 状态展示 ---------- */

  function showState(message) {
    gateEl.hidden = true;
    contentEl.hidden = true;
    stateEl.hidden = false;
    stateEl.textContent = '';
    var p = document.createElement('p');
    p.className = 'empty-state';
    p.textContent = message;
    stateEl.appendChild(p);
  }

  function showGateError(message) {
    gateError.hidden = false;
    gateError.textContent = message;
  }

  /* ---------- 正文渲染 ---------- */

  function renderContent(data) {
    document.title = data.title + ' · 个人笔记';
    titleEl.textContent = data.title;

    metaEl.innerHTML =
      '<span>作者：' + window.escapeHtml(data.author) + '</span>'
      + '<span aria-hidden="true">·</span>'
      + '<span>更新：' + window.escapeHtml(window.formatDateTime(data.updated_at)) + '</span>';

    // 正文经 renderMarkdown 清洗后再注入，避免脚本执行
    bodyEl.innerHTML = window.renderMarkdown(data.content);

    favoriteBtn.textContent = data.favorited ? '★ 已收藏' : '☆ 收藏';
    favoriteBtn.dataset.noteId = String(data.id);

    // 评论区占位：Phase 5 填充真实列表与输入框
    commentsEl.hidden = false;
    commentsEl.innerHTML = '<p class="empty-state">评论区即将开放</p>';

    gateEl.hidden = true;
    stateEl.hidden = true;
    contentEl.hidden = false;
  }

  /* ---------- 取正文（可选密码） ---------- */

  function fetchContent(password) {
    var payload = password === undefined ? {} : { password: password };
    window.api.post('/api/share/' + encodeURIComponent(token), payload)
      .then(renderContent)
      .catch(function (error) {
        if (error && error.status === 403) {
          showGateError(STR.wrongPassword);
          gateInput.focus();
          gateInput.select();
          return;
        }
        if (error && error.status === 404) {
          showState(STR.missing);
          return;
        }
        showState(STR.failed);
      });
  }

  /* ---------- 加载元信息 ---------- */

  function load() {
    if (!token) {
      showState(STR.invalid);
      return;
    }
    window.api.get('/api/share/' + encodeURIComponent(token))
      .then(function (meta) {
        if (meta.need_password) {
          gateEl.hidden = false;
          gateInput.focus();
        } else {
          fetchContent(undefined);
        }
      })
      .catch(function (error) {
        if (error && error.status === 404) {
          showState(STR.missing);
          return;
        }
        showState(STR.failed);
      });
  }

  /* ---------- 交互 ---------- */

  gateBtn.addEventListener('click', function () {
    gateError.hidden = true;
    fetchContent(gateInput.value);
  });

  gateInput.addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
      gateError.hidden = true;
      fetchContent(gateInput.value);
    }
  });

  // 未登录点收藏 → 跳登录（Phase 5 接入收藏接口）
  favoriteBtn.addEventListener('click', function () {
    if (!currentUser) {
      window.location.href = loginUrl();
      return;
    }
    window.toast('收藏功能即将开放');
  });

  renderNav();
  load();
})();

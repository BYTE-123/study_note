/* 个人笔记 · 顶部导航渲染与登录态探测
 * 导出：renderNav(user, options) / initNav(options) —— 主页与后续所有内页复用。
 * 主页导航不含「退出」；内页传入 { withLogout: true } 时追加「退出」按钮。
 */
(function (global) {
  'use strict';

  var GUEST_LINKS = [
    { label: '登录', href: '/login' },
    { label: '注册', href: '/register' },
    { label: '关于', href: '/about' }
  ];

  var USER_LINKS = [
    { label: '我的文章', href: '/notes' },
    { label: '个人主页', href: '/profile' },
    { label: '关于', href: '/about' }
  ];

  function linkEl(item) {
    var a = document.createElement('a');
    a.textContent = item.label;
    a.href = item.href;
    return a;
  }

  /** 「退出」按钮：登出成功后回主页。 */
  function logoutEl() {
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-ghost btn-sm';
    button.textContent = '退出';
    button.addEventListener('click', function () {
      button.disabled = true;
      global.api.post('/api/auth/logout').then(function () {
        window.location.href = '/';
      }).catch(function () {
        button.disabled = false;
      });
    });
    return button;
  }

  /**
   * 渲染导航链接。
   * @param {?{id:number,username:string}} user 当前登录用户，null 表示未登录
   * @param {{withLogout?: boolean}} [options]
   */
  function renderNav(user, options) {
    var container = document.querySelector('.app-nav__links');
    if (!container) {
      return;
    }
    options = options || {};
    var links = user ? USER_LINKS : GUEST_LINKS;

    container.textContent = '';
    links.forEach(function (item) {
      container.appendChild(linkEl(item));
    });
    if (user && options.withLogout) {
      container.appendChild(logoutEl());
    }
  }

  /** 探测登录态：401 属正常情况，不弹提示。 */
  function fetchUser() {
    return fetch('/api/auth/me', { credentials: 'include' })
      .then(function (response) {
        return response.ok ? response.json() : null;
      })
      .then(function (payload) {
        return payload && payload.code === 'OK' ? payload.data : null;
      })
      .catch(function () {
        return null;
      });
  }

  /**
   * 探测登录态并渲染导航。
   * @param {{withLogout?: boolean}} [options]
   * @returns {Promise<?object>} 当前用户，未登录为 null
   */
  function initNav(options) {
    return fetchUser().then(function (user) {
      renderNav(user, options);
      return user;
    });
  }

  global.renderNav = renderNav;
  global.initNav = initNav;
})(window);

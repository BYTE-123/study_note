/* 个人笔记 · 顶部导航渲染与登录态探测
 * 导出：renderNav(user, options) / initNav(options) / initShareNav() —— 全站复用。
 * 主页与内页共用同一渲染器；内页传 { withLogout: true } 时追加「退出」按钮。
 * <768px 时链接折叠为汉堡菜单（契约 10.2 响应式）。
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

  /** 页面路径是否命中导航项（用于选中态）。 */
  function isActive(href) {
    var path = global.location.pathname;
    if (href === '/') {
      return path === '/' || path === '/index.html';
    }
    return path === href || path.indexOf(href + '/') === 0;
  }

  function linkEl(item) {
    var a = document.createElement('a');
    a.textContent = item.label;
    a.href = item.href;
    if (isActive(item.href)) {
      a.classList.add('is-active');
      a.setAttribute('aria-current', 'page');
    }
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

  /** 汉堡按钮：仅在 <768px 可见，点击展开/收起链接区。 */
  function ensureToggle(nav, container) {
    if (!container.id) {
      container.id = 'app-nav-links';
    }
    var toggle = nav.querySelector('.app-nav__toggle');
    if (toggle) {
      return toggle;
    }
    toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'app-nav__toggle';
    toggle.setAttribute('aria-label', '展开导航菜单');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-controls', container.id);
    toggle.innerHTML = '<span class="app-nav__toggle-icon" aria-hidden="true">☰</span>';

    function setOpen(open) {
      container.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', open ? '收起导航菜单' : '展开导航菜单');
    }

    toggle.addEventListener('click', function () {
      setOpen(!container.classList.contains('is-open'));
    });
    // 点击链接后收起；Esc 收起
    container.addEventListener('click', function (event) {
      if (event.target.tagName === 'A') {
        setOpen(false);
      }
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && container.classList.contains('is-open')) {
        setOpen(false);
        toggle.focus();
      }
    });
    nav.appendChild(toggle);
    return toggle;
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
    var nav = container.closest('.app-nav') || container.parentNode;
    var links = user ? USER_LINKS : GUEST_LINKS;

    container.textContent = '';
    links.forEach(function (item) {
      container.appendChild(linkEl(item));
    });
    if (user && options.withLogout) {
      container.appendChild(logoutEl());
    }
    if (nav) {
      ensureToggle(nav, container);
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

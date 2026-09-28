/* 个人笔记 · 个人主页
 * 职责：并发拉取 profile / favorites / notes 三份数据，分别渲染三张卡；
 *       每张卡独立处理加载 / 空 / 失败态；「编辑资料」行内编辑并调 PUT /api/profile。
 * 安全：标题、昵称、作者、简介一律经 escapeHtml / textContent 输出。
 */
(function () {
  'use strict';

  var TEXTS = {
    loading: '加载中…',
    failed: '加载失败，请稍后重试',
    retry: '重试',
    emptyFavorites: '还没有收藏，去发现好内容吧',
    emptyHistory: '还没有笔记，点击「新建文章」开始记录吧',
    noBio: '这个人很懒，还没有写简介',
    self: '我',
    unavailable: '内容已失效',
    unavailableToast: '该笔记已取消分享',
    saved: '已保存'
  };

  var BIO_MAX = 200;

  var profileContent = document.getElementById('profile-content');
  var favoritesContent = document.getElementById('favorites-content');
  var historyContent = document.getElementById('history-content');
  var editBtn = document.getElementById('edit-profile-btn');

  var currentProfile = null;

  function gotoLogin() {
    window.location.href = '/login?next=' + encodeURIComponent(
      window.location.pathname + window.location.search);
  }

  function statusTag(status) {
    var published = status === 'published';
    return '<span class="tag' + (published ? ' tag-published' : '') + '">'
      + (published ? '已发布' : '草稿') + '</span>';
  }

  function showLoading(container) {
    container.innerHTML = '<p class="state-block">' + TEXTS.loading + '</p>';
  }

  function showEmpty(container, message) {
    container.textContent = '';
    var p = document.createElement('p');
    p.className = 'empty-state';
    p.textContent = message;
    container.appendChild(p);
  }

  function showError(container, onRetry) {
    container.textContent = '';
    var block = document.createElement('div');
    block.className = 'state-block';

    var text = document.createElement('p');
    text.textContent = TEXTS.failed;

    var retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'btn btn-sm';
    retry.textContent = TEXTS.retry;
    retry.addEventListener('click', onRetry);

    block.appendChild(text);
    block.appendChild(retry);
    container.appendChild(block);
  }

  function handleError(container, error, onRetry) {
    if (error && error.status === 401) {
      gotoLogin();
      return;
    }
    showError(container, onRetry);
  }

  /* ---------- 个人信息 ---------- */

  function renderProfile(data) {
    currentProfile = data;
    profileContent.textContent = '';

    var dl = document.createElement('dl');
    dl.className = 'profile-info';

    function row(label, value) {
      var dt = document.createElement('dt');
      dt.textContent = label;
      var dd = document.createElement('dd');
      dd.textContent = value;
      dl.appendChild(dt);
      dl.appendChild(dd);
    }

    row('昵称', data.username);
    row('邮箱', data.email);
    row('注册时间', window.formatDateTime(data.created_at));
    row('简介', data.bio || TEXTS.noBio);

    profileContent.appendChild(dl);
    editBtn.hidden = false;
  }

  function renderProfileForm() {
    var data = currentProfile || {};
    profileContent.textContent = '';

    var form = document.createElement('form');
    form.className = 'profile-form';
    form.innerHTML =
      '<label class="profile-field"><span>昵称</span>'
      + '<input class="profile-input" name="username" maxlength="20" required>'
      + '</label>'
      + '<label class="profile-field"><span>简介</span>'
      + '<textarea class="profile-input" name="bio" rows="3" maxlength="200"></textarea>'
      + '</label>'
      + '<p class="profile-error" hidden></p>'
      + '<div class="profile-form__actions">'
      + '<button class="btn btn-primary" type="submit">保存</button>'
      + '<button class="btn" type="button" data-cancel>取消</button>'
      + '</div>';

    var usernameInput = form.elements.username;
    var bioInput = form.elements.bio;
    var errorEl = form.querySelector('.profile-error');
    var saveBtn = form.querySelector('button[type="submit"]');

    usernameInput.value = data.username || '';
    bioInput.value = data.bio || '';

    form.querySelector('[data-cancel]').addEventListener('click', function () {
      renderProfile(currentProfile);
    });

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var bio = bioInput.value;
      if (bio.length > BIO_MAX) {
        errorEl.hidden = false;
        errorEl.textContent = '简介最多 200 字';
        return;
      }
      errorEl.hidden = true;
      saveBtn.disabled = true;
      window.api.put('/api/profile', {
        username: usernameInput.value.trim(),
        bio: bio
      }).then(function (updated) {
        renderProfile(updated);
        window.toast(TEXTS.saved);
      }).catch(function (error) {
        if (error && error.status === 401) {
          gotoLogin();
          return;
        }
        errorEl.hidden = false;
        errorEl.textContent = (error && error.message) || TEXTS.failed;
        saveBtn.disabled = false;
      });
    });

    profileContent.appendChild(form);
    usernameInput.focus();
  }

  function loadProfile() {
    editBtn.hidden = true;
    showLoading(profileContent);
    window.api.get('/api/profile')
      .then(renderProfile)
      .catch(function (error) {
        handleError(profileContent, error, loadProfile);
      });
  }

  /* ---------- 我的收藏 ---------- */

  function renderFavorites(data) {
    var items = (data && data.items) || [];
    favoritesContent.textContent = '';
    if (!items.length) {
      showEmpty(favoritesContent, TEXTS.emptyFavorites);
      return;
    }

    var list = document.createElement('div');
    list.className = 'profile-list';

    items.forEach(function (item) {
      var row = document.createElement('a');
      row.className = 'fav-item' + (item.is_available ? '' : ' is-unavailable');

      if (item.is_available) {
        row.href = '/note?id=' + encodeURIComponent(item.note_id);
      } else {
        row.href = '#';
        row.addEventListener('click', function (event) {
          event.preventDefault();
          window.toast(TEXTS.unavailableToast);
        });
      }

      var owner = item.is_self ? TEXTS.self : item.owner;
      row.innerHTML =
        '<span class="fav-item__head">'
        + '<span class="fav-item__title">' + window.escapeHtml(item.title) + '</span>'
        + (item.is_available
          ? '' : '<span class="tag fav-item__badge">' + TEXTS.unavailable + '</span>')
        + '</span>'
        + '<span class="fav-item__meta">'
        + '<span>' + window.escapeHtml(owner) + '</span>'
        + '<span aria-hidden="true">·</span>'
        + '<span>' + window.escapeHtml(window.formatDateTime(item.created_at)) + '</span>'
        + '</span>';

      list.appendChild(row);
    });

    favoritesContent.appendChild(list);
  }

  function loadFavorites() {
    showLoading(favoritesContent);
    window.api.get('/api/favorites')
      .then(renderFavorites)
      .catch(function (error) {
        handleError(favoritesContent, error, loadFavorites);
      });
  }

  /* ---------- 笔记历史 ---------- */

  function renderHistory(data) {
    var items = (data && data.items) || [];
    historyContent.textContent = '';
    if (!items.length) {
      showEmpty(historyContent, TEXTS.emptyHistory);
      return;
    }

    var list = document.createElement('div');
    list.className = 'profile-list';

    items.forEach(function (item) {
      var link = document.createElement('a');
      link.className = 'history-item';
      link.href = '/note?id=' + encodeURIComponent(item.id);
      link.innerHTML =
        '<span class="history-item__title">' + window.escapeHtml(item.title) + '</span>'
        + '<span class="history-item__meta">' + statusTag(item.status)
        + '<span>' + window.escapeHtml(window.formatDateTime(item.updated_at)) + '</span>'
        + '</span>';
      list.appendChild(link);
    });

    historyContent.appendChild(list);
  }

  function loadHistory() {
    showLoading(historyContent);
    window.api.get('/api/notes?page=1&page_size=50')
      .then(renderHistory)
      .catch(function (error) {
        handleError(historyContent, error, loadHistory);
      });
  }

  /* ---------- 初始化 ---------- */

  editBtn.addEventListener('click', renderProfileForm);

  window.initNav({ withLogout: true }).then(function (user) {
    if (!user) {
      gotoLogin();
      return;
    }
    // 三张卡各自独立并发加载
    loadProfile();
    loadFavorites();
    loadHistory();
  });
})();

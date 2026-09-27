/* 个人笔记 · 笔记详情
 * 职责：读取 ?id= 拉取详情 → 渲染标题/状态/时间/正文（renderMarkdown 防 XSS）；
 *       编辑跳编辑器，删除二次确认后回列表；401 跳登录，404 显示「资源不存在」。
 * marked 来源：/static/js/vendor/marked.min.js（v12.0.2，npmmirror 构建）。
 */
(function () {
  'use strict';

  var noteId = new URLSearchParams(window.location.search).get('id');

  var cardEl = document.getElementById('note-card');
  var titleEl = document.getElementById('note-title');
  var metaEl = document.getElementById('note-meta');
  var bodyEl = document.getElementById('note-body');
  var actionsEl = document.getElementById('note-actions');
  var editLink = document.getElementById('edit-link');
  var deleteBtn = document.getElementById('delete-btn');
  var errorEl = document.getElementById('note-error');

  // 分享设置面板
  var shareCard = document.getElementById('share-card');
  var shareCollapse = document.getElementById('share-collapse');
  var shareBody = document.getElementById('share-body');
  var shareSwitch = document.getElementById('share-switch');
  var shareLinkRow = document.getElementById('share-link-row');
  var shareLink = document.getElementById('share-link');
  var copyBtn = document.getElementById('copy-btn');
  var sharePassword = document.getElementById('share-password');
  var savePasswordBtn = document.getElementById('save-password-btn');

  // 评论区（comments-ui.js 渲染）
  var commentPanel = document.getElementById('comment-panel');
  // 收藏按钮
  var favoriteBtn = document.getElementById('favorite-btn');

  var CONFIRM_TEXT = '删除后不可恢复，确定删除这篇笔记吗？';

  function statusTag(status) {
    var published = status === 'published';
    return '<span class="tag' + (published ? ' tag-published' : '') + '">'
      + (published ? '已发布' : '草稿') + '</span>';
  }

  function gotoLogin() {
    window.location.href = '/login?next=' + encodeURIComponent(
      window.location.pathname + window.location.search);
  }

  function renderNote(note) {
    document.title = note.title + ' · 个人笔记';
    titleEl.textContent = note.title;
    metaEl.innerHTML =
      statusTag(note.status)
      + '<span>创建：' + window.escapeHtml(window.formatDateTime(note.created_at)) + '</span>'
      + '<span aria-hidden="true">·</span>'
      + '<span>更新：' + window.escapeHtml(window.formatDateTime(note.updated_at)) + '</span>';

    // 正文经 renderMarkdown 清洗后再注入，避免脚本执行
    bodyEl.innerHTML = window.renderMarkdown(note.content);

    editLink.href = '/editor?id=' + encodeURIComponent(note.id);
    actionsEl.hidden = false;
    setFavorite(note.favorited);
    renderShare(note);
    loadComments();
  }

  /* ---------- 收藏按钮（心形：未收藏线性、已收藏填充主色） ---------- */

  function setFavorite(favorited) {
    favoriteBtn.classList.toggle('is-active', !!favorited);
    favoriteBtn.setAttribute('aria-pressed', String(!!favorited));
    favoriteBtn.querySelector('.fav-btn__icon').textContent = favorited ? '♥' : '♡';
    favoriteBtn.querySelector('.fav-btn__text').textContent = favorited ? '已收藏' : '收藏';
  }

  favoriteBtn.addEventListener('click', function () {
    favoriteBtn.disabled = true;
    window.api.post('/api/notes/' + encodeURIComponent(noteId) + '/favorite')
      .then(function (data) {
        setFavorite(data.favorited);
        window.toast(data.favorited ? '已加入收藏' : '已取消收藏');
      })
      .catch(function (error) {
        if (error && error.status === 401) {
          gotoLogin();
        }
      })
      .then(function () {
        favoriteBtn.disabled = false;
      });
  });

  function showBlock(message, withBack) {
    cardEl.hidden = true;
    errorEl.hidden = false;
    errorEl.textContent = '';

    var text = document.createElement('p');
    text.className = 'empty-state';
    text.textContent = message;
    errorEl.appendChild(text);

    if (withBack) {
      var back = document.createElement('a');
      back.className = 'btn btn-sm';
      back.href = '/notes';
      back.textContent = '返回列表';
      errorEl.appendChild(back);
    }
  }

  function load() {
    window.api.get('/api/notes/' + encodeURIComponent(noteId)).then(renderNote).catch(function (error) {
      if (error && error.status === 401) {
        gotoLogin();
        return;
      }
      if (error && error.status === 404) {
        showBlock('资源不存在', true);
        return;
      }
      showBlock('加载失败，请稍后重试', true);
    });
  }

  deleteBtn.addEventListener('click', function () {
    if (!window.confirm(CONFIRM_TEXT)) {
      return;
    }
    deleteBtn.disabled = true;
    window.api.del('/api/notes/' + encodeURIComponent(noteId)).then(function () {
      window.toast('已删除');
      window.location.href = '/notes';
    }).catch(function (error) {
      deleteBtn.disabled = false;
      if (error && error.status === 401) {
        gotoLogin();
      }
    });
  });

  window.initNav({ withLogout: true });

  /* ---------- 分享设置面板 ---------- */

  var COPY_RESET_MS = 1500;

  function shareUrlFor(token) {
    return window.location.origin + '/share.html?token=' + encodeURIComponent(token);
  }

  /** 依据分享状态刷新开关、链接区显隐与链接值。 */
  function applyShareState(data) {
    var shared = !!data.is_shared;
    shareSwitch.checked = shared;
    shareLinkRow.hidden = !shared;
    if (shared && data.share_token) {
      shareLink.value = shareUrlFor(data.share_token);
    } else {
      shareLink.value = '';
    }
  }

  function renderShare(note) {
    shareCard.hidden = false;
    applyShareState({
      is_shared: note.is_shared,
      share_token: note.share_token
    });
  }

  shareCollapse.addEventListener('click', function () {
    var collapsed = !shareBody.hidden;
    shareBody.hidden = collapsed;
    shareCollapse.textContent = collapsed ? '展开' : '收起';
    shareCollapse.setAttribute('aria-expanded', String(!collapsed));
  });

  // 开关切换：开启/关闭分享
  shareSwitch.addEventListener('change', function () {
    shareSwitch.disabled = true;
    window.api.put('/api/notes/' + encodeURIComponent(noteId) + '/share',
      { enabled: shareSwitch.checked })
      .then(function (data) {
        applyShareState(data);
        window.toast(data.is_shared ? '已开启分享' : '已关闭分享');
      })
      .catch(function (error) {
        // 回滚开关视觉状态
        shareSwitch.checked = !shareSwitch.checked;
        if (error && error.status === 401) {
          gotoLogin();
        }
      })
      .then(function () {
        shareSwitch.disabled = false;
      });
  });

  // 复制链接：成功后按钮变「已复制」1.5s；剪贴板不可用则选中文本
  copyBtn.addEventListener('click', function () {
    var text = shareLink.value;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        var original = copyBtn.textContent;
        copyBtn.textContent = '已复制';
        setTimeout(function () {
          copyBtn.textContent = original;
        }, COPY_RESET_MS);
      }).catch(function () {
        shareLink.select();
      });
    } else {
      shareLink.select();
    }
  });

  // 保存密码：空值 → null（移除密码）；非空 → 设置密码并确保分享开启
  savePasswordBtn.addEventListener('click', function () {
    var value = sharePassword.value;
    var payload = { enabled: true, password: value === '' ? null : value };
    savePasswordBtn.disabled = true;
    window.api.put('/api/notes/' + encodeURIComponent(noteId) + '/share', payload)
      .then(function (data) {
        applyShareState(data);
        sharePassword.value = '';
        window.toast(value === '' ? '已移除密码' : '密码已保存');
      })
      .catch(function (error) {
        if (error && error.status === 401) {
          gotoLogin();
        }
      })
      .then(function () {
        savePasswordBtn.disabled = false;
      });
  });

  /* ---------- 评论区（契约 10.4：加载/空/有评论/提交/超长） ---------- */

  function commentsUrl() {
    return '/api/notes/' + encodeURIComponent(noteId) + '/comments';
  }

  // 详情页仅作者可达：可发表、可管理开关、可删除本人评论
  function commentOptions() {
    return {
      editable: true,
      canManage: true,
      canDelete: function (comment) { return !!comment.is_self; },
      onToggle: function (enabled) {
        return window.api.put(
          '/api/notes/' + encodeURIComponent(noteId) + '/comment-setting',
          { enabled: enabled }
        ).then(function (data) {
          // 开关变化后重渲染，关闭时输入框切换为「评论已关闭」
          loadComments();
          return data;
        });
      },
      onSubmit: function (content) {
        return window.api.post(commentsUrl(), { content: content });
      },
      onDelete: function (commentId) {
        return window.api.del('/api/comments/' + encodeURIComponent(commentId));
      }
    };
  }

  function loadComments() {
    window.CommentsUI.renderLoading(commentPanel);
    window.api.get(commentsUrl()).then(function (data) {
      window.CommentsUI.renderComments(commentPanel, data, commentOptions());
    }).catch(function (error) {
      if (error && error.status === 401) {
        gotoLogin();
        return;
      }
      commentPanel.hidden = false;
      commentPanel.textContent = '';
      var block = document.createElement('p');
      block.className = 'empty-state';
      block.textContent = '评论加载失败，请稍后重试';
      commentPanel.appendChild(block);
    });
  }

  if (noteId) {
    load();
  } else {
    showBlock('资源不存在', true);
  }
})();

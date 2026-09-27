/* 个人笔记 · 评论组件（详情页与分享页共用，DRY）
 * 导出：window.CommentsUI = { renderLoading, renderComments, bindCommentBox, MAX_LEN }
 *
 * renderComments(container, data, options)
 *   data    {comments_enabled: boolean, items: [{id, user:{id,username}, content, created_at, is_self}]}
 *   options {
 *     editable?:  boolean            当前访问者是否可发表（未登录 false）
 *     loginUrl?:  string             不可发表时「登录后可评论」的跳转地址
 *     canManage?: boolean            是否显示「评论已开启」开关（仅作者）
 *     canDelete?: (comment) => bool  是否显示某条评论的删除图标，缺省用 is_self
 *     onToggle?:  (enabled) => Promise
 *     onSubmit?:  (content) => Promise<新评论结构>
 *     onDelete?:  (commentId, comment) => Promise
 *   }
 *   返回 {append, remove} 控制器（submit 成功后自动插入，无需调用方处理）。
 *
 * bindCommentBox(container, options)
 *   在 container 内构建输入区（输入框 + 「发布」按钮），处理长度提示与提交态；
 *   提交成功后调用 options.onSubmitted(comment)。
 *
 * 安全：用户文本一律经 window.escapeHtml 转义后再插入 DOM（后端存原文）。
 */
(function (global) {
  'use strict';

  var MAX_LEN = 500;

  var TEXTS = {
    empty: '还没有评论，来说两句吧',
    closed: '评论已关闭',
    login: '登录后可评论',
    placeholder: '写下你的评论…',
    submit: '发布',
    submitting: '发布中…',
    tooLong: '评论最多 500 字',
    switchLabel: '评论已开启'
  };

  function makeEl(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text != null) {
      node.textContent = text;
    }
    return node;
  }

  /** 加载态骨架：两行灰块，避免空白闪烁。 */
  function renderLoading(container) {
    container.hidden = false;
    container.textContent = '';

    var card = makeEl('article', 'card comment-card');
    card.appendChild(makeEl('div', 'comment-skeleton skeleton'));
    card.appendChild(makeEl('div', 'comment-skeleton skeleton comment-skeleton--short'));
    container.appendChild(card);
  }

  /** 评论开关（仅作者可见可操作）。 */
  function buildSwitch(enabled, onToggle) {
    var wrap = makeEl('label', 'comment-switch');

    var input = document.createElement('input');
    input.type = 'checkbox';
    input.setAttribute('role', 'switch');
    input.setAttribute('aria-label', TEXTS.switchLabel);
    input.checked = !!enabled;

    var track = makeEl('span', 'comment-switch__track');
    var text = makeEl('span', 'comment-switch__text', TEXTS.switchLabel);

    input.addEventListener('change', function () {
      input.disabled = true;
      Promise.resolve(onToggle ? onToggle(input.checked) : null)
        .then(function (data) {
          // 调用方通常重渲染；此处仅在返回开关状态时同步一次
          if (data && typeof data.comments_enabled !== 'undefined') {
            input.checked = !!data.comments_enabled;
          }
        })
        .catch(function () {
          input.checked = !input.checked;
        })
        .then(function () {
          input.disabled = false;
        });
    });

    wrap.appendChild(input);
    wrap.appendChild(track);
    wrap.appendChild(text);
    return wrap;
  }

  /** 单条评论行：昵称 + 时间 + 内容 +（本人的）删除图标。 */
  function buildItem(item, options, controller) {
    var row = makeEl('div', 'comment-item');
    row.setAttribute('data-comment-id', String(item.id));

    var user = item.user || {};
    var head = makeEl('div', 'comment-item__head');
    head.innerHTML =
      '<span class="comment-item__name">' + global.escapeHtml(user.username || '') + '</span>'
      + '<span class="comment-item__time">'
      + global.escapeHtml(global.formatDateTime(item.created_at)) + '</span>';
    row.appendChild(head);

    row.appendChild(makeEl('p', 'comment-item__content', ''));
    // 内容经 escapeHtml 后再注入，保留换行由 CSS white-space 处理
    row.querySelector('.comment-item__content').innerHTML =
      global.escapeHtml(item.content || '');

    var deletable = options.canDelete
      ? !!options.canDelete(item)
      : !!(item && item.is_self);
    if (deletable && options.onDelete) {
      var del = makeEl('button', 'comment-delete', '✕');
      del.type = 'button';
      del.title = '删除评论';
      del.setAttribute('aria-label', '删除评论');
      del.addEventListener('click', function () {
        del.disabled = true;
        Promise.resolve(options.onDelete(item.id, item))
          .then(function () {
            controller.remove(item.id);
          })
          .catch(function () {
            del.disabled = false;
          });
      });
      head.appendChild(del);
    }

    return row;
  }

  /**
   * 输入区：输入框 + 「发布」。未开启评论 → 「评论已关闭」；
   * 未登录（editable=false）→ 「登录后可评论」按钮。
   */
  function bindCommentBox(container, options) {
    options = options || {};
    var box = makeEl('div', 'comment-box');

    if (options.enabled === false) {
      box.appendChild(makeEl('p', 'comment-closed', TEXTS.closed));
      container.appendChild(box);
      return box;
    }

    if (options.editable === false) {
      var login = makeEl('a', 'btn btn-primary', TEXTS.login);
      login.href = options.loginUrl || '/login';
      box.appendChild(login);
      container.appendChild(box);
      return box;
    }

    var textarea = document.createElement('textarea');
    textarea.className = 'comment-input';
    textarea.rows = 3;
    textarea.setAttribute('placeholder', TEXTS.placeholder);
    textarea.setAttribute('aria-label', TEXTS.placeholder);

    var tip = makeEl('p', 'comment-tip', TEXTS.tooLong);
    tip.hidden = true;

    var button = makeEl('button', 'btn btn-primary comment-submit', TEXTS.submit);
    button.type = 'button';

    var inputWrap = makeEl('div', 'comment-input-wrap');
    inputWrap.appendChild(textarea);
    inputWrap.appendChild(tip);

    var actions = makeEl('div', 'comment-box__actions');
    actions.appendChild(button);

    function refresh() {
      var tooLong = textarea.value.trim().length > MAX_LEN;
      tip.hidden = !tooLong;
      button.disabled = tooLong || textarea.value.trim() === '';
    }

    /** 提交成功后统一复位按钮与输入框（不阻塞列表更新）。 */
    function settle() {
      button.textContent = TEXTS.submit;
      refresh();
    }

    textarea.addEventListener('input', refresh);

    button.addEventListener('click', function () {
      var content = textarea.value.trim();
      if (!content || content.length > MAX_LEN) {
        refresh();
        return;
      }
      button.disabled = true;
      button.textContent = TEXTS.submitting;

      Promise.resolve(options.onSubmit ? options.onSubmit(content) : null)
        .then(function (comment) {
          textarea.value = '';
          if (comment && options.onSubmitted) {
            options.onSubmitted(comment);
          }
          settle();
        })
        .catch(function () {
          // 错误提示由 api.js 统一 toast；这里只恢复可编辑状态
          settle();
        });
    });

    box.appendChild(inputWrap);
    box.appendChild(actions);
    container.appendChild(box);
    refresh();
    return box;
  }

  function renderComments(container, data, options) {
    options = options || {};
    var enabled = !(data && data.comments_enabled === false);
    var items = ((data && data.items) || []).slice();

    container.hidden = false;
    container.textContent = '';

    var card = makeEl('article', 'card comment-card');

    var head = makeEl('div', 'comment-head');
    var title = makeEl('h2', 'comment-title');
    head.appendChild(title);
    if (options.canManage) {
      head.appendChild(buildSwitch(enabled, options.onToggle));
    }
    card.appendChild(head);

    var list = makeEl('div', 'comment-list');
    card.appendChild(list);

    function updateTitle() {
      title.textContent = '评论（' + items.length + '）';
    }

    function renderEmpty() {
      list.textContent = '';
      list.appendChild(makeEl('p', 'comment-empty', TEXTS.empty));
    }

    function renderList() {
      list.textContent = '';
      if (!items.length) {
        renderEmpty();
        return;
      }
      items.forEach(function (item) {
        list.appendChild(buildItem(item, options, controller));
      });
    }

    var controller = {
      append: function (comment) {
        if (!comment) {
          return;
        }
        items.push(comment);
        if (items.length === 1) {
          list.textContent = '';
        }
        list.appendChild(buildItem(comment, options, controller));
        updateTitle();
      },
      remove: function (id) {
        items = items.filter(function (item) {
          return item.id !== id;
        });
        var node = list.querySelector('[data-comment-id="' + id + '"]');
        if (node && node.parentNode) {
          node.parentNode.removeChild(node);
        }
        if (!items.length) {
          renderEmpty();
        }
        updateTitle();
      }
    };

    renderList();
    updateTitle();

    bindCommentBox(card, {
      enabled: enabled,
      editable: options.editable,
      loginUrl: options.loginUrl,
      onSubmit: options.onSubmit,
      onSubmitted: function (comment) {
        controller.append(comment);
      }
    });

    container.appendChild(card);
    return controller;
  }

  global.CommentsUI = {
    MAX_LEN: MAX_LEN,
    renderLoading: renderLoading,
    renderComments: renderComments,
    bindCommentBox: bindCommentBox
  };
})(window);

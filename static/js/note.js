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
  }

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

  if (noteId) {
    load();
  } else {
    showBlock('资源不存在', true);
  }
})();

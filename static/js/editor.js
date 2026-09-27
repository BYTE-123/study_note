/* 个人笔记 · 编辑器
 * 职责：
 * - Markdown 工具栏：在选区处包裹语法或在行首加前缀，插入后保持/重设光标；
 * - 预览切换：marked 解析后经 window.renderMarkdown 清洗（防 XSS）；
 * - 保存：新建 POST、编辑 PUT，草稿提示「已保存」，发布跳详情页。
 * marked 来源：/static/js/vendor/marked.min.js（v12.0.2，npmmirror 构建）。
 */
(function () {
  'use strict';

  var titleInput = document.getElementById('title');
  var tagsInput = document.getElementById('tags');
  var contentInput = document.getElementById('content');
  var previewEl = document.getElementById('preview');
  var previewBtn = document.getElementById('preview-toggle');
  var saveDraftBtn = document.getElementById('save-draft');
  var publishBtn = document.getElementById('publish');
  var imageInput = document.getElementById('image-input');
  var imageBtn = document.querySelector('.editor-toolbar [data-syntax="image"]');

  if (!contentInput) {
    return;
  }

  var noteId = new URLSearchParams(window.location.search).get('id');
  var previewing = false;

  /* wrap:true → 选区两侧包裹；否则在行首加前缀 */
  var SYNTAX = {
    h1: { prefix: '# ' },
    h2: { prefix: '## ' },
    bold: { wrap: true, before: '**', after: '**', placeholder: '加粗文字' },
    italic: { wrap: true, before: '*', after: '*', placeholder: '斜体文字' },
    code: { wrap: true, before: '`', after: '`', placeholder: '代码' },
    quote: { prefix: '> ' },
    ul: { prefix: '- ' },
    ol: { prefix: '1. ' },
    link: { wrap: true, before: '[', after: '](url)', placeholder: '文字' },
    image: { wrap: true, before: '![', after: '](url)', placeholder: '描述' }
  };

  /* ---------- 插入语法 ---------- */

  function setSelection(start, end) {
    contentInput.focus();
    contentInput.setSelectionRange(start, end);
  }

  function wrapSelection(spec) {
    var value = contentInput.value;
    var start = contentInput.selectionStart;
    var end = contentInput.selectionEnd;
    var inner = value.slice(start, end) || spec.placeholder;

    contentInput.value = value.slice(0, start) + spec.before + inner + spec.after + value.slice(end);
    // 光标/选区落在内部文本上，便于直接替换
    setSelection(start + spec.before.length, start + spec.before.length + inner.length);
  }

  function prefixLines(prefix) {
    var value = contentInput.value;
    var start = contentInput.selectionStart;
    var end = contentInput.selectionEnd;
    var lineStart = value.lastIndexOf('\n', start - 1) + 1;
    var block = value.slice(lineStart, end);
    var prefixed = block.split('\n').map(function (line) {
      return prefix + line;
    }).join('\n');

    contentInput.value = value.slice(0, lineStart) + prefixed + value.slice(end);
    setSelection(lineStart, lineStart + prefixed.length);
  }

  /** 按类型在光标处插入 Markdown 语法。 */
  function insertSyntax(type) {
    var spec = SYNTAX[type];
    if (!spec) {
      return;
    }
    if (spec.wrap) {
      wrapSelection(spec);
    } else {
      prefixLines(spec.prefix);
    }
  }

  /** 在光标处插入纯文本（如 ``![文件名](url)``），插入后光标落在末尾。 */
  function insertTextAtCaret(text) {
    var value = contentInput.value;
    var start = contentInput.selectionStart;
    var end = contentInput.selectionEnd;
    contentInput.value = value.slice(0, start) + text + value.slice(end);
    var caret = start + text.length;
    setSelection(caret, caret);
  }

  /* ---------- 图片上传 ---------- */

  /** 选文件 → 上传 → 在光标处插入 ``![文件名](url)``；失败时恢复按钮。 */
  function uploadImage(file) {
    // 上传进行中忽略重复触发，避免按钮文案被后一次覆盖而卡在「上传中…」
    if (imageBtn.disabled) {
      return;
    }
    var originalText = imageBtn.textContent;
    imageBtn.disabled = true;
    imageBtn.textContent = '上传中…';

    window.api.upload(file).then(function (data) {
      insertTextAtCaret('![' + file.name + '](' + data.url + ')');
    }).catch(function (error) {
      // 失败文案已由 api.js 统一 toast（含 401「请先登录」与接口 message）
      if (error && error.status === 401) {
        gotoLogin();
      }
    }).then(function () {
      imageBtn.disabled = false;
      imageBtn.textContent = originalText;
      if (imageInput) {
        imageInput.value = '';
      }
    });
  }

  if (imageInput && imageBtn) {
    imageInput.addEventListener('change', function () {
      if (imageInput.files && imageInput.files[0]) {
        uploadImage(imageInput.files[0]);
      }
    });
  }

  Array.prototype.forEach.call(
    document.querySelectorAll('.editor-toolbar [data-syntax]'),
    function (btn) {
      btn.addEventListener('click', function () {
        var type = btn.getAttribute('data-syntax');
        if (type === 'image') {
          // 图片走文件选择 + 上传，不插入占位语法
          if (imageInput) {
            imageInput.click();
          }
          return;
        }
        insertSyntax(type);
      });
    }
  );

  /* ---------- 预览切换 ---------- */

  function togglePreview() {
    previewing = !previewing;
    previewEl.hidden = !previewing;
    contentInput.hidden = previewing;
    previewBtn.setAttribute('aria-pressed', String(previewing));
    previewBtn.classList.toggle('is-active', previewing);
    previewBtn.textContent = previewing ? '✎ 编辑' : '👁 预览';
    if (previewing) {
      // 渲染用户正文，必须经过 renderMarkdown 清洗
      previewEl.innerHTML = window.renderMarkdown(contentInput.value);
    }
  }

  previewBtn.addEventListener('click', togglePreview);

  /* ---------- 保存 ---------- */

  function gotoLogin() {
    window.location.href = '/login?next=' + encodeURIComponent(
      window.location.pathname + window.location.search);
  }

  function setLoading(loading) {
    saveDraftBtn.disabled = loading;
    publishBtn.disabled = loading;
  }

  function save(status, btn) {
    var originalText = btn.textContent;
    setLoading(true);
    btn.textContent = '保存中…';

    var payload = {
      title: titleInput.value,
      content: contentInput.value,
      tags: tagsInput.value,
      status: status
    };
    var request = noteId
      ? window.api.put('/api/notes/' + encodeURIComponent(noteId), payload)
      : window.api.post('/api/notes', payload);

    request.then(function (data) {
      if (!noteId) {
        noteId = data.id;
        // 记住 id，后续保存即变为编辑
        window.history.replaceState(null, '', '/editor?id=' + encodeURIComponent(noteId));
      }
      if (status === 'published') {
        window.location.href = '/note?id=' + encodeURIComponent(noteId);
        return;
      }
      setLoading(false);
      btn.textContent = originalText;
      window.toast('已保存');
    }).catch(function (error) {
      setLoading(false);
      btn.textContent = originalText;
      if (error && error.status === 401) {
        gotoLogin();
      }
    });
  }

  saveDraftBtn.addEventListener('click', function () {
    save('draft', saveDraftBtn);
  });

  publishBtn.addEventListener('click', function () {
    save('published', publishBtn);
  });

  /* ---------- 编辑模式：回填 ---------- */

  function loadNote() {
    window.api.get('/api/notes/' + encodeURIComponent(noteId)).then(function (note) {
      titleInput.value = note.title || '';
      tagsInput.value = note.tags || '';
      contentInput.value = note.content || '';
    }).catch(function (error) {
      if (error && error.status === 401) {
        gotoLogin();
      }
    });
  }

  window.initNav({ withLogout: true });

  if (noteId) {
    loadNote();
  }
})();

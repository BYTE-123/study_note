/* 个人笔记 · AI 润色（契约 10.2 弹窗布局 / 10.4 交互细节 / 10.5 可访问性）
 * 职责：
 * - 正文区划词 → 自定义右键菜单（仅在有非空选区时出现）；
 * - 左右对比弹窗：左「原文」只读、右「润色结果」流式逐字出现；
 * - 「确认替换」仅替换原选区，「取消」不改动正文；出错展示中文文案并允许重试；
 * - 键盘可达：Shift+F10 / 菜单键唤起菜单，弹窗内 Tab 循环、Esc 关闭。
 */
(function () {
  'use strict';

  var MENU_VIEWPORT_GAP = 8;
  var DEFAULT_ERROR = 'AI 服务暂时不可用，请稍后重试';

  var menuEl = document.getElementById('editor-context-menu');
  var modalEl = document.getElementById('polish-modal');
  var dialogEl = modalEl && modalEl.querySelector('.polish-dialog');
  var sourceEl = document.getElementById('polish-source');
  var resultEl = document.getElementById('polish-result');
  var stateEl = document.getElementById('polish-state');
  var spinnerEl = document.getElementById('polish-spinner');
  var stateTextEl = document.getElementById('polish-state-text');
  var retryBtn = document.getElementById('polish-retry');
  var applyBtn = document.getElementById('polish-apply');
  var cancelBtn = document.getElementById('polish-cancel');
  var closeBtn = document.getElementById('polish-close');

  var textareaEl = null;
  var selection = null;       // {start, end, text}
  var controller = null;
  var lastFocused = null;
  var loading = false;

  if (!menuEl || !modalEl || !resultEl) {
    return;
  }

  /* ---------- 右键菜单 ---------- */

  function hideMenu() {
    menuEl.hidden = true;
  }

  /** 定位到 (x, y)，超出视口时回收，保证菜单完整可见。 */
  function showMenuAt(x, y) {
    menuEl.hidden = false;
    var rect = menuEl.getBoundingClientRect();
    var left = Math.min(x, window.innerWidth - rect.width - MENU_VIEWPORT_GAP);
    var top = Math.min(y, window.innerHeight - rect.height - MENU_VIEWPORT_GAP);
    menuEl.style.left = Math.max(MENU_VIEWPORT_GAP, left) + 'px';
    menuEl.style.top = Math.max(MENU_VIEWPORT_GAP, top) + 'px';
  }

  /** 取当前非空选区；无选区或纯空白 → null。 */
  function readSelection(textarea) {
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    if (end <= start) {
      return null;
    }
    var text = textarea.value.slice(start, end);
    if (!text.trim()) {
      return null;
    }
    return { start: start, end: end, text: text };
  }

  /** 有非空选区才弹菜单（返回是否已弹出）。 */
  function openMenuFrom(textarea, x, y) {
    var current = readSelection(textarea);
    if (!current) {
      return false;
    }
    selection = current;
    showMenuAt(x, y);
    var item = menuEl.querySelector('[data-action="polish"]');
    if (item) {
      item.focus();
    }
    return true;
  }

  function initContextMenu(textarea) {
    if (!textarea) {
      return;
    }
    textareaEl = textarea;

    textarea.addEventListener('contextmenu', function (event) {
      if (openMenuFrom(textarea, event.clientX, event.clientY)) {
        event.preventDefault();   // 仅在划词时接管浏览器菜单
      } else {
        hideMenu();
      }
    });

    // 键盘唤起（契约 10.5）：Shift+F10 或键盘「菜单键」
    textarea.addEventListener('keydown', function (event) {
      var isMenuKey = event.key === 'ContextMenu'
        || (event.shiftKey && event.key === 'F10');
      if (!isMenuKey) {
        return;
      }
      var rect = textarea.getBoundingClientRect();
      if (openMenuFrom(textarea, rect.left + 24, rect.top + 24)) {
        event.preventDefault();
      }
    });

    menuEl.querySelector('[data-action="polish"]').addEventListener('click', function () {
      var target = selection;
      hideMenu();
      if (target) {
        openPolishModal(target);
      }
    });

    document.addEventListener('click', function (event) {
      if (!menuEl.hidden && !menuEl.contains(event.target)) {
        hideMenu();
      }
    });
    document.addEventListener('scroll', hideMenu, true);
    window.addEventListener('resize', hideMenu);
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !menuEl.hidden) {
        hideMenu();
      }
    });
  }

  /* ---------- 弹窗状态 ---------- */

  /** loading：转圈 + 文案；error：红色文案 + 重试；idle：整体收起。 */
  function setState(mode, message) {
    if (mode === 'idle') {
      stateEl.hidden = true;
      return;
    }
    stateEl.hidden = false;
    spinnerEl.hidden = mode !== 'loading';
    stateTextEl.textContent = message;
    stateTextEl.classList.toggle('is-error', mode === 'error');
    retryBtn.hidden = mode !== 'error';
  }

  function setApplyEnabled(enabled) {
    applyBtn.disabled = !enabled;
  }

  function abortStream() {
    if (controller) {
      controller.abort();
      controller = null;
    }
  }

  /** 收集弹窗内当前可聚焦元素（隐藏与禁用的自动排除）。 */
  function focusables() {
    return Array.prototype.slice.call(
      modalEl.querySelectorAll('button:not([hidden]):not(:disabled)'));
  }

  function onModalKeydown(event) {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeModal();
      return;
    }
    if (event.key !== 'Tab') {
      return;
    }
    var items = focusables();
    if (!items.length) {
      return;
    }
    var first = items[0];
    var last = items[items.length - 1];
    if (event.shiftKey && (document.activeElement === first
      || !modalEl.contains(document.activeElement))) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function closeModal(options) {
    if (modalEl.hidden) {
      return;
    }
    options = options || {};
    abortStream();
    loading = false;
    selection = null;          // 让在途回调失效
    modalEl.hidden = true;
    document.body.classList.remove('is-modal-open');
    document.removeEventListener('keydown', onModalKeydown, true);
    if (options.restoreFocus !== false && lastFocused && lastFocused.focus) {
      lastFocused.focus();
    }
  }

  function startStream() {
    abortStream();
    controller = window.AbortController ? new AbortController() : null;

    var target = selection;
    resultEl.textContent = '';
    setApplyEnabled(false);
    setState('loading', '润色中…');
    loading = true;

    window.streamPolish(target.text, {
      onDelta: function (chunk) {
        if (selection !== target) {
          return;                // 已关闭或已换选区，丢弃过期数据
        }
        if (loading) {
          loading = false;
          setState('idle');
        }
        resultEl.textContent += chunk;
        resultEl.scrollTop = resultEl.scrollHeight;
        setApplyEnabled(true);   // 流式过程中也可提前采用
      },
      onError: function (message) {
        if (selection !== target) {
          return;
        }
        loading = false;
        setState('error', message || DEFAULT_ERROR);
      },
      onDone: function () {
        if (selection !== target) {
          return;
        }
        loading = false;
        setState('idle');
      },
      signal: controller ? controller.signal : undefined
    }).catch(function () {
      // 网络中断已由 onError 兜底，这里只需吞掉未处理的 rejection
    });
  }

  function openPolishModal(target) {
    selection = target;
    lastFocused = document.activeElement;
    sourceEl.textContent = target.text;
    modalEl.hidden = false;
    document.body.classList.add('is-modal-open');
    document.addEventListener('keydown', onModalKeydown, true);
    if (dialogEl) {
      dialogEl.focus();          // 焦点移入弹窗（契约 10.5）
    }
    startStream();               // 打开即请求
  }

  /** 用右栏当前文本替换 textarea 的 [start, end) 区间。 */
  function applyResult() {
    if (!textareaEl || !selection) {
      return;
    }
    var replacement = resultEl.textContent;
    if (!replacement) {
      return;
    }
    var value = textareaEl.value;
    var start = Math.min(selection.start, value.length);
    var end = Math.min(selection.end, value.length);
    var caret = start + replacement.length;

    textareaEl.value = value.slice(0, start) + replacement + value.slice(end);
    textareaEl.focus();
    textareaEl.setSelectionRange(caret, caret);
    textareaEl.dispatchEvent(new Event('input', { bubbles: true }));
    closeModal({ restoreFocus: false });
  }

  /* ---------- 事件绑定 ---------- */

  closeBtn.addEventListener('click', function () {
    closeModal();
  });
  cancelBtn.addEventListener('click', function () {
    closeModal();
  });
  applyBtn.addEventListener('click', applyResult);
  retryBtn.addEventListener('click', startStream);
  modalEl.addEventListener('click', function (event) {
    if (event.target === modalEl) {
      closeModal();              // 点击遮罩关闭，不改动正文
    }
  });

  window.initContextMenu = initContextMenu;
})();

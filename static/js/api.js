/* 个人笔记 · 统一请求封装与提示
 * 约定：所有接口返回 {code, message, data}；code !== 'OK' 时提示中文 message 并抛错。
 */
(function (global) {
  'use strict';

  var DEFAULT_ERROR = '服务器开小差了，请稍后重试';
  var NETWORK_ERROR = '网络异常，请检查连接';

  /** 转义用户文本，避免 XSS（渲染用户输入时一律经过它）。 */
  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /**
   * 时间格式化：ISO 字符串（``2026-06-17T14:33:00``）→ ``2026-06-17 14:33``。
   * @param {string} value 服务端返回的时间字符串
   * @returns {string}
   */
  function formatDateTime(value) {
    var text = String(value == null ? '' : value);
    return text.length >= 16 ? text.slice(0, 16).replace('T', ' ') : text;
  }

  /** 危险节点：Markdown 渲染结果中一律移除。 */
  var FORBIDDEN_TAGS = 'script,style,iframe,object,embed,form,link,meta,base';

  /** 危险协议：href/src 命中即移除该属性（http/https/相对路径/mailto 放行）。 */
  var DANGEROUS_SCHEME = /^(?:javascript|data|vbscript):/i;

  /**
   * 渲染 Markdown 为安全 HTML（编辑器预览与笔记详情共用）。
   *
   * marked v12 返回的是原始 HTML，必须自行清洗：
   * 1. marked.parse 解析源码；
   * 2. DOMParser 转为游离文档（其中的 script 不会执行）；
   * 3. 删除危险节点，移除 on* / srcdoc 属性，过滤 javascript: / data: 协议；
   * 4. 返回 body.innerHTML（已是安全 HTML 字符串）。
   *
   * @param {string} md Markdown 源码
   * @returns {string} 清洗后的 HTML
   */
  function renderMarkdown(md) {
    var source = String(md == null ? '' : md);

    // marked 未加载时退化为纯文本，宁可少渲染也不引入风险
    if (typeof global.marked === 'undefined' || !global.marked.parse) {
      return '<p>' + escapeHtml(source) + '</p>';
    }

    var doc = new DOMParser().parseFromString(global.marked.parse(source), 'text/html');

    Array.prototype.forEach.call(doc.body.querySelectorAll(FORBIDDEN_TAGS), function (node) {
      if (node.parentNode) {
        node.parentNode.removeChild(node);
      }
    });

    Array.prototype.forEach.call(doc.body.querySelectorAll('*'), function (el) {
      Array.prototype.slice.call(el.attributes).forEach(function (attr) {
        var name = attr.name.toLowerCase();
        if (name.indexOf('on') === 0 || name === 'srcdoc') {
          el.removeAttribute(attr.name);
        } else if ((name === 'href' || name === 'src')
          && DANGEROUS_SCHEME.test(String(attr.value || '').trim())) {
          el.removeAttribute(attr.name);
        }
      });
      if (el.tagName === 'IMG') {
        el.setAttribute('loading', 'lazy');
      }
    });

    return doc.body.innerHTML;
  }

  /** 右下角提示，2.5s 后自动消失。type: 'info' | 'error' */
  function toast(message, type) {
    var el = document.createElement('div');
    el.className = 'toast' + (type === 'error' ? ' toast-error' : '');
    el.setAttribute('role', 'status');
    el.textContent = message;
    document.body.appendChild(el);

    requestAnimationFrame(function () {
      el.classList.add('is-visible');
    });

    setTimeout(function () {
      el.classList.remove('is-visible');
      setTimeout(function () {
        if (el.parentNode) {
          el.parentNode.removeChild(el);
        }
      }, 250);
    }, 2500);
  }

  /**
   * 统一请求。
   * @param {string} method HTTP 方法
   * @param {string} url    接口地址
   * @param {{json?: *, formData?: FormData}} [options]
   * @returns {Promise<*>} 成功时解析 data
   */
  async function request(method, url, options) {
    options = options || {};

    var init = { method: method, credentials: 'include' };
    if (options.formData) {
      init.body = options.formData;
    } else if (Object.prototype.hasOwnProperty.call(options, 'json')) {
      init.headers = { 'Content-Type': 'application/json' };
      init.body = JSON.stringify(options.json);
    }

    var response;
    try {
      response = await fetch(url, init);
    } catch (error) {
      toast(NETWORK_ERROR, 'error');
      throw error;
    }

    var payload;
    try {
      payload = await response.json();
    } catch (error) {
      toast(NETWORK_ERROR, 'error');
      throw error;
    }

    if (!payload || payload.code !== 'OK') {
      var message = (payload && payload.message) || DEFAULT_ERROR;
      toast(message, 'error');
      // 附加错误码与 HTTP 状态，供页面区分 401/404 等分支
      var apiError = new Error(message);
      apiError.code = payload && payload.code;
      apiError.status = response.status;
      throw apiError;
    }

    return payload.data;
  }

  var api = {
    request: request,
    get: function (url) {
      return request('GET', url);
    },
    post: function (url, json) {
      return request('POST', url, { json: json });
    },
    put: function (url, json) {
      return request('PUT', url, { json: json });
    },
    del: function (url) {
      return request('DELETE', url);
    },
    /** 上传图片，返回 {url}。 */
    upload: function (file) {
      var formData = new FormData();
      formData.append('file', file);
      return request('POST', '/api/upload', { formData: formData });
    }
  };

  /* ---------- AI 润色流式请求 ---------- */

  /** 解析单帧负载（已去掉 "data: " 前缀）。 */
  function dispatchFrame(payload, handlers, flags) {
    if (payload === '[DONE]') {
      flags.finished = true;
      // 已经出过错就不再宣告「完成」，否则界面会盖掉错误提示与「重试」
      if (!flags.failed && handlers.onDone) {
        handlers.onDone();
      }
      return;
    }

    var data;
    try {
      data = JSON.parse(payload);
    } catch (error) {
      return; // 脏帧不中断整条流
    }

    if (data && typeof data.delta === 'string') {
      if (handlers.onDelta) {
        handlers.onDelta(data.delta);
      }
    } else if (data && data.error) {
      flags.failed = true;
      if (handlers.onError) {
        handlers.onError(data.error);
      }
    }
  }

  /** 逐个读出 SSE 帧并按 ``\n\n`` 边界切分。 */
  function readFrames(response, handlers) {
    var reader = response.body.getReader();
    var decoder = new TextDecoder('utf-8');
    var buffer = '';
    var flags = { finished: false, failed: false };

    function handleBlock(block) {
      block.split('\n').forEach(function (line) {
        if (line.indexOf('data:') === 0) {
          dispatchFrame(line.slice(5).trim(), handlers, flags);
        }
      });
    }

    function pump() {
      return reader.read().then(function (result) {
        if (result.done) {
          if (buffer.trim()) {
            handleBlock(buffer);
          }
          // 服务端异常/中断没发 [DONE] 时也要收尾，避免加载态卡住
          if (!flags.finished && !flags.failed && handlers.onDone) {
            handlers.onDone();
          }
          return;
        }
        buffer += decoder.decode(result.value, { stream: true });
        var blocks = buffer.split('\n\n');
        buffer = blocks.pop();
        blocks.forEach(function (block) {
          if (block.trim()) {
            handleBlock(block);
          }
        });
        return pump();
      });
    }

    return pump();
  }

  /** 与统一响应结构一致的失败分支：toast 中文 message，401 额外跳登录。 */
  async function handleStreamFailure(response, handlers) {
    var payload = null;
    try {
      payload = await response.json();
    } catch (error) {
      payload = null;
    }
    var message = (payload && payload.message) || DEFAULT_ERROR;

    toast(message, 'error');
    if (response.status === 401) {
      window.location.href = '/login?next=' + encodeURIComponent(
        window.location.pathname + window.location.search);
    }
    if (handlers.onError) {
      handlers.onError(message);
    }
  }

  /**
   * 流式润色：POST /api/ai/polish，边收边回调。
   * @param {string} text 选中的原文
   * @param {{onDelta?: Function, onError?: Function, onDone?: Function,
   *          signal?: AbortSignal}} [handlers]
   * @returns {Promise<void>}
   */
  async function streamPolish(text, handlers) {
    handlers = handlers || {};

    var response;
    try {
      response = await fetch('/api/ai/polish', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text }),
        signal: handlers.signal
      });
    } catch (error) {
      // 用户主动中断（关闭弹窗）不当作错误
      if (error && error.name === 'AbortError') {
        return;
      }
      toast(NETWORK_ERROR, 'error');
      if (handlers.onError) {
        handlers.onError(NETWORK_ERROR);
      }
      return;
    }

    if (!response.ok) {
      await handleStreamFailure(response, handlers);
      return;
    }

    await readFrames(response, handlers);
  }

  global.toast = toast;
  global.api = api;
  global.streamPolish = streamPolish;
  global.escapeHtml = escapeHtml;
  global.renderMarkdown = renderMarkdown;
  global.formatDateTime = formatDateTime;
})(window);

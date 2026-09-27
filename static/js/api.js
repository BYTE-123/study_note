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

  global.toast = toast;
  global.api = api;
  global.escapeHtml = escapeHtml;
  global.renderMarkdown = renderMarkdown;
  global.formatDateTime = formatDateTime;
})(window);

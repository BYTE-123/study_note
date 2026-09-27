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
      throw new Error(message);
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
})(window);

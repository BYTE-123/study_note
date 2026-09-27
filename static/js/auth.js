/* 个人笔记 · 登录 / 注册页交互
 * 职责：客户端预校验（不发请求）、按钮加载态、成功后跳转、失败展示接口 message。
 * 约定：页面 <body data-page="login|register"> 区分形态。
 */
(function () {
  'use strict';

  var EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  var form = document.getElementById('auth-form');
  if (!form) {
    return;
  }

  var page = document.body.getAttribute('data-page') === 'register' ? 'register' : 'login';
  var submitBtn = document.getElementById('auth-submit');
  var formError = document.getElementById('form-error');
  var defaultBtnText = submitBtn ? submitBtn.textContent : '';
  var loadingText = page === 'register' ? '注册中…' : '登录中…';

  /* ---------- 取值与提示 ---------- */

  function rawValue(name) {
    var el = form.querySelector('[name="' + name + '"]');
    return el ? String(el.value || '') : '';
  }

  function value(name) {
    return rawValue(name).trim();
  }

  function clearErrors() {
    Array.prototype.forEach.call(form.querySelectorAll('.field'), function (el) {
      el.classList.remove('is-error');
    });
    Array.prototype.forEach.call(form.querySelectorAll('.field-error'), function (el) {
      el.textContent = '';
    });
    if (formError) {
      formError.textContent = '';
      formError.hidden = true;
    }
  }

  /** 在指定输入框下显示中文提示，并给字段加错误态描边。 */
  function setFieldError(name, message) {
    var wrap = form.querySelector('[data-field="' + name + '"]');
    var box = document.getElementById(name + '-error');
    if (wrap) {
      wrap.classList.add('is-error');
    }
    if (box) {
      box.textContent = message;
    }
  }

  /** 表单顶部错误提示（取接口 message）。 */
  function showFormError(message) {
    if (!formError) {
      return;
    }
    formError.textContent = message;
    formError.hidden = false;
  }

  /* ---------- 客户端预校验：不通过则完全不发请求 ---------- */

  function validate() {
    clearErrors();
    var valid = true;

    var email = value('email');
    if (!email) {
      setFieldError('email', '请输入邮箱');
      valid = false;
    } else if (!EMAIL_RE.test(email)) {
      setFieldError('email', '请输入正确的邮箱地址');
      valid = false;
    }

    var password = rawValue('password');
    if (!password) {
      setFieldError('password', '请输入密码');
      valid = false;
    }

    if (page === 'register') {
      var username = value('username');
      if (!username) {
        setFieldError('username', '请输入用户名');
        valid = false;
      } else if (username.length < 2 || username.length > 20) {
        setFieldError('username', '用户名需为 2-20 个字符');
        valid = false;
      }

      if (password && password.length < 6) {
        setFieldError('password', '密码长度至少 6 位');
        valid = false;
      }

      var confirmPassword = rawValue('confirm_password');
      if (!confirmPassword) {
        setFieldError('confirm_password', '请再次输入密码');
        valid = false;
      } else if (confirmPassword !== password) {
        setFieldError('confirm_password', '两次输入的密码不一致');
        valid = false;
      }
    }

    return valid;
  }

  /* ---------- 按钮加载态 ---------- */

  function setLoading(loading) {
    if (!submitBtn) {
      return;
    }
    submitBtn.disabled = loading;
    submitBtn.textContent = loading ? loadingText : defaultBtnText;
  }

  /* ---------- 跳转目标：?next= 以 / 开头时优先 ---------- */

  function targetAfterSuccess() {
    var next = '';
    try {
      next = new URLSearchParams(window.location.search).get('next') || '';
    } catch (error) {
      next = '';
    }
    return next.charAt(0) === '/' ? next : '/workbench';
  }

  function handleFailure(error) {
    setLoading(false);
    showFormError((error && error.message) || '操作失败，请稍后重试');
  }

  /* ---------- 提交 ---------- */

  function doLogin() {
    return window.api.post('/api/auth/login', {
      email: value('email'),
      password: rawValue('password')
    });
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();

    if (!validate()) {
      return;
    }

    setLoading(true);

    if (page === 'register') {
      // 必须先注册成功，再调用登录（api.post 会立即发起请求，故用函数延后）
      window.api.post('/api/auth/register', {
        email: value('email'),
        username: value('username'),
        password: rawValue('password'),
        confirm_password: rawValue('confirm_password')
      }).then(doLogin).then(function () {
        window.location.href = targetAfterSuccess();
      }).catch(handleFailure);
    } else {
      doLogin().then(function () {
        window.location.href = targetAfterSuccess();
      }).catch(handleFailure);
    }
  });

  /* ---------- 已登录则直接进入工作台（原生 fetch，避免 401 弹提示） ---------- */

  fetch('/api/auth/me', { credentials: 'include' })
    .then(function (response) {
      return response.ok ? response.json() : null;
    })
    .then(function (payload) {
      if (payload && payload.code === 'OK' && payload.data) {
        window.location.href = targetAfterSuccess();
      }
    })
    .catch(function () {
      /* 未登录或网络异常：停留在当前页 */
    });
})();

/* 个人笔记 · 主页交互
 * 职责：渲染导航、按登录态决定「开始记录」去向、「了解更多」平滑滚动。
 */
(function () {
  'use strict';

  var startBtn = document.getElementById('start-btn');
  var moreBtn = document.getElementById('more-btn');
  var features = document.getElementById('features');

  // 未登录 → 去注册；已登录 → 直接进工作台
  window.initNav().then(function (user) {
    if (startBtn) {
      startBtn.setAttribute('href', user ? '/workbench' : '/register');
    }
  });

  // 了解更多：平滑滚动到特性区（特性区不可用时回退到 /about）
  if (moreBtn && features) {
    moreBtn.addEventListener('click', function (event) {
      event.preventDefault();
      features.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }
})();

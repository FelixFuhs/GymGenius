const QuickStart = {
  checkFirstTime() {
    if (!localStorage.getItem('gg_first_time')) {
      document.getElementById('onboarding-modal').classList.add('show');
    }
  },
  start() {
    localStorage.setItem('gg_first_time', 'no');
    document.getElementById('onboarding-modal').classList.remove('show');
  }
};

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('qs-start-btn');
  if (btn) {
    btn.addEventListener('click', QuickStart.start);
  }
  QuickStart.checkFirstTime();
});

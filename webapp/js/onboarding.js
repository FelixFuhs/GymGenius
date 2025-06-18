const QuickStart = (() => {
    const KEY = 'gg_first_time';

    function showModal() {
        const modal = document.getElementById('onboarding-modal');
        if (!modal) return;
        modal.classList.add('show');
        const btn = modal.querySelector('#qs-start-btn');
        if (btn) {
            btn.addEventListener('click', finish, { once: true });
        }
    }

    function finish() {
        localStorage.setItem(KEY, 'no');
        const modal = document.getElementById('onboarding-modal');
        if (modal) modal.classList.remove('show');
        window.location.hash = '#exercises';
    }

    function checkFirstTime() {
        if (!localStorage.getItem(KEY)) {
            showModal();
        }
    }

    return { checkFirstTime };
})();

window.QuickStart = QuickStart;

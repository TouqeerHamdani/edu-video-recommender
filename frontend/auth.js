// --- Auth page logic ---

const loginTab = document.getElementById('loginTab');
const registerTab = document.getElementById('registerTab');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const authMessage = document.getElementById('authMessage');

// Tab switching
loginTab.addEventListener('click', () => {
    loginTab.classList.add('active');
    registerTab.classList.remove('active');
    loginForm.classList.add('active');
    registerForm.classList.remove('active');
    authMessage.textContent = '';
});

registerTab.addEventListener('click', () => {
    registerTab.classList.add('active');
    loginTab.classList.remove('active');
    registerForm.classList.add('active');
    loginForm.classList.remove('active');
    authMessage.textContent = '';
});

// --- Login ---
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    authMessage.textContent = '';
    authMessage.classList.remove('auth-success');

    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();

        if (res.ok) {
            authMessage.textContent = 'Login successful! Redirecting...';
            authMessage.classList.add('auth-success');
            setTimeout(() => { window.location.href = '/'; }, 1000);
        } else {
            authMessage.textContent = data.detail || data.error || 'Login failed.';
        }
    } catch (err) {
        authMessage.textContent = 'Network error. Please try again.';
    }
});

// --- Register ---
registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    authMessage.textContent = '';
    authMessage.classList.remove('auth-success');

    const email = document.getElementById('registerEmail').value.trim();
    const password = document.getElementById('registerPassword').value;

    try {
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();

        if (res.ok) {
            authMessage.textContent = 'Registration successful! You can now log in.';
            authMessage.classList.add('auth-success');
            setTimeout(() => { loginTab.click(); }, 1500);
        } else {
            authMessage.textContent = data.detail || data.error || 'Registration failed.';
        }
    } catch (err) {
        authMessage.textContent = 'Network error. Please try again.';
    }
});
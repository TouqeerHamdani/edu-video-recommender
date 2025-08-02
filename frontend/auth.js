// Toggle between login and register forms
const loginTab = document.getElementById('loginTab');
const registerTab = document.getElementById('registerTab');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const authMessage = document.getElementById('authMessage');

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

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    authMessage.textContent = '';
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (res.ok) {
            localStorage.setItem('token', data.token);
            localStorage.setItem('username', data.username);
            authMessage.textContent = 'Login successful! Redirecting...';
            authMessage.classList.add('auth-success');
            setTimeout(() => { window.location.href = '/'; }, 1200);
        } else {
            authMessage.textContent = data.error || 'Login failed.';
            authMessage.classList.remove('auth-success');
        }
    } catch (err) {
        authMessage.textContent = 'Network error.';
        authMessage.classList.remove('auth-success');
    }
});

registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    authMessage.textContent = '';
    const username = document.getElementById('registerUsername').value.trim();
    const email = document.getElementById('registerEmail').value.trim();
    const password = document.getElementById('registerPassword').value;
    try {
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password })
        });
        const data = await res.json();
        if (res.ok) {
            authMessage.textContent = 'Registration successful! You can now log in.';
            authMessage.classList.add('auth-success');
            setTimeout(() => {
                loginTab.click();
            }, 1200);
        } else {
            authMessage.textContent = data.error || 'Registration failed.';
            authMessage.classList.remove('auth-success');
        }
    } catch (err) {
        authMessage.textContent = 'Network error.';
        authMessage.classList.remove('auth-success');
    }
}); 
// --- Shared auth check (used on all pages) ---
async function checkAuth() {
  try {
    const res = await fetch('/api/me', { credentials: 'include' });
    if (res.ok) {
      const data = await res.json();
      return data;
    }
  } catch (e) {
    // Not logged in or network error
  }
  return null;
}

async function updateNav() {
  const loginBtn = document.getElementById('loginBtn');
  const userInfo = document.getElementById('userInfo');
  const userEmail = document.getElementById('userEmail');
  const logoutBtn = document.getElementById('logoutBtn');

  if (!loginBtn || !userInfo) return;

  const user = await checkAuth();
  if (user && user.email) {
    loginBtn.style.display = 'none';
    userInfo.style.display = 'inline';
    if (userEmail) userEmail.textContent = user.email;

    if (logoutBtn) {
      // Use onclick assignment to prevent duplicate handlers on repeated calls
      logoutBtn.onclick = async (e) => {
        e.preventDefault();
        try {
          await fetch('/api/logout', { method: 'POST', credentials: 'include' });
        } catch (err) {
          // Ignore errors
        }
        window.location.href = '/';
      };
    }
  } else {
    loginBtn.style.display = 'inline';
    userInfo.style.display = 'none';
  }
}

// Run nav update on load
updateNav();

// --- Search functionality ---
const searchBtn = document.getElementById("searchBtn");
if (searchBtn) {
  searchBtn.addEventListener("click", () => {
    const searchInputEl = document.getElementById("searchInput");
    if (!searchInputEl) return;
    const query = searchInputEl.value.trim();
    const durationSelect = document.getElementById("durationSelect");
    const duration = durationSelect ? durationSelect.value : "any";

    if (!query) {
      alert("Please enter a search query.");
      return;
    }

    window.location.href = `/results?query=${encodeURIComponent(query)}&duration=${encodeURIComponent(duration)}`;
  });
}

// Allow Enter key to trigger search
const searchInput = document.getElementById("searchInput");
if (searchInput) {
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && searchBtn) {
      searchBtn.click();
    }
  });
}

// --- Home page: Nav scroll effect ---
const homeNav = document.getElementById("homeNav");
if (homeNav) {
  window.addEventListener("scroll", () => {
    homeNav.classList.toggle("scrolled", window.scrollY > 40);
  });
}

// --- Home page: Quick topic tags ---
document.querySelectorAll(".tag[data-query]").forEach(tag => {
  tag.addEventListener("click", () => {
    const query = tag.getAttribute("data-query");
    const input = document.getElementById("searchInput");
    if (input) input.value = query;
    if (searchBtn) searchBtn.click();
  });
});

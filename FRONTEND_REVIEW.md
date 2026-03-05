# Frontend Flow Review

Although the task mentioned Next.js, the current frontend is built with vanilla HTML, JavaScript, and CSS and served by FastAPI. I have reviewed the existing vanilla frontend code. Here are the issues identified regarding flow, routing, state management, and UX:

## 1. Sign-in / Authentication Flow

*   **Missing Redirect Post-Login (UX/Flow Issue)**
    *   **File:** `frontend/auth.js` (lines 60-66)
    *   **Issue:** After a successful login, the user is statically redirected to `/`. If a user is on `/results` or `/video`, gets a 401 unauthorized, and is sent to `/auth`, they lose their place after logging in. There is no `?next=` or `?redirect=` parameter handling.
    *   **Suggested Fix:** Capture the current URL before redirecting to `/auth` (e.g., `/auth?next=/video?videoId=123`), and upon successful login in `auth.js`, read the `next` parameter from the URL to redirect them back to where they were.
*   **Stale Auth State on Logout (State Management)**
    *   **File:** `frontend/project.js` (lines 31-40)
    *   **Issue:** The `logoutBtn.onclick` handler catches errors but ignores them. If the network is down and the `/api/logout` call fails, the client is redirected to `/`, but their cookie/session might still be valid or in a weird state.
    *   **Suggested Fix:** Provide feedback if logout fails, or clear local state regardless of the server response to ensure the UI updates consistently.
*   **Missing Logout Redirection Logic (Flow Issue)**
    *   **File:** `frontend/project.js` (line 38)
    *   **Issue:** Logout simply redirects to `/`. While often fine, if the user was on a public page (like `/results` for a generic query that doesn't strictly require auth), forcing them back to the home page disrupts their flow. If they were on a protected page, redirecting to `/auth` or `/` is correct.
    *   **Suggested Fix:** Check if the current page requires auth before redirecting to `/`, or simply reload the current page.

## 2. Page Navigation and Routing

*   **Dead-end State on Invalid Video IDs**
    *   **File:** `frontend/video.html` (lines 92-100)
    *   **Issue:** The script checks `if (videoId && /^[\w-]+$/.test(videoId))` and inserts the iframe. If the video ID is missing or invalid, nothing happens. The page remains blank with just the title and "Like" button, offering no explanation or way back (other than the footer link).
    *   **Suggested Fix:** Add an `else` branch to display a user-friendly error message ("Invalid or missing video ID") and a clear button to return to the search or home page.
*   **Missing "Back" Button UX**
    *   **File:** `frontend/video.html`, `frontend/results.html`
    *   **Issue:** Both pages only have a simple text link `Back to Home` in the footer. If a user clicks a video from `/results`, they often want to go back to *their search results*, not the home page.
    *   **Suggested Fix:** Add a standard browser `history.back()` link or keep track of the last search query to provide a "Back to Results" button on the video page.

## 3. Component State Management

*   **Stale Nav State (FOUC / Flickering)**
    *   **File:** `frontend/project.js` (lines 2-47)
    *   **Issue:** `updateNav()` runs on load and makes an async fetch to `/api/me`. While this happens, the UI shows the "Login" button by default. If the user is logged in, there's a visible flicker as the Login button disappears and the user info appears.
    *   **Suggested Fix:** Hide the auth nav area entirely until the `checkAuth()` fetch completes, or use a loading spinner in the nav.
*   **Missing Loading States for Interactions**
    *   **File:** `frontend/video.html` (lines 118-154)
    *   **Issue:** When clicking the "Like" button, there's a network request. There is no loading state or disabled state on the button during this request. The user could click it multiple times rapidly.
    *   **Suggested Fix:** Disable the `likeBtn` immediately on click and add a loading spinner or text (e.g., "Liking..."). Re-enable it if the request fails.
*   **Unhandled Empty Search State**
    *   **File:** `frontend/project.js` (lines 59-62)
    *   **Issue:** Submitting an empty search query uses a native `alert("Please enter a search query.")`. This is a poor UX.
    *   **Suggested Fix:** Use inline validation, such as a red outline on the input or a small text message below the search bar.

## 4. Demo Page and Sign-in Component UX

*   **Sign-in/Register Tab Confusion**
    *   **File:** `frontend/auth.html`, `frontend/auth.js`
    *   **Issue:** The "Registration successful! You can now log in." message relies on a `setTimeout` to click the login tab. However, the message itself disappears when the tab is clicked because `authMessage.textContent = '';` runs in the tab switch event listener. The user never actually sees the success message on the login tab.
    *   **Suggested Fix:** Do not clear the `authMessage` when switching tabs if the message is a success message, or explicitly set the success message *after* switching the tab.
*   **Missing Password Visibility Toggle**
    *   **File:** `frontend/auth.html`
    *   **Issue:** Standard UX for password fields includes an "eye" icon to show/hide the password. This is missing, making it harder for users to verify what they typed, especially on mobile.
    *   **Suggested Fix:** Add a toggle button inside the password inputs to change `type="password"` to `type="text"`.
*   **Search Box Overlap/Responsiveness**
    *   **File:** `frontend/results.html`, `frontend/video.html`
    *   **Issue:** The `.topbar` has a `.search-box` and `#authNav`. On smaller screens (mobile), these elements might overlap or become too cramped because they use inline styling for `margin-left: auto;` and float-like behavior.
    *   **Suggested Fix:** Use a robust Flexbox layout with `flex-wrap` or hide the search bar behind an icon on mobile devices.

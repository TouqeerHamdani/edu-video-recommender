const fs = require('fs');
let code = fs.readFileSync('frontend/results.js', 'utf8');

// Update renderResults function
let oldRender = `  function renderResults(data) {
        resultsSection.innerHTML = "";

        if (!data.results || data.results.length === 0) {
          resultsSection.innerHTML = "<p style='text-align:center;'>No results found.</p>";
          return;
        }

        data.results.forEach(video => {`;

let newRender = `  function renderResults(data, isPolling = false) {
        if (!isPolling) {
          resultsSection.innerHTML = "";
        } else {
          // If polling, we don't clear the section, we just update it.
          // To avoid re-rendering existing videos, we could just clear and re-render everything
          // since the number of items is small (<= 10). This keeps it simple and ensures correct ordering.
          resultsSection.innerHTML = "";
        }

        if (!data.results || data.results.length === 0) {
          if (!isPolling) {
             resultsSection.innerHTML = "<p style='text-align:center;'>No results found in database. Searching the web...</p>";
          }
          return;
        }

        data.results.forEach(video => {`;

code = code.replace(oldRender, newRender);


// Update fetch logic
let oldFetch = `    if (!cacheHit) {
      const apiUrl = \`/api/recommend?query=\${encodeURIComponent(query)}&duration=\${encodeURIComponent(duration)}\`;
      fetch(apiUrl, { credentials: 'include' })
        .then(res => {
          if (res.status === 401) {
            window.location.href = '/auth';
            throw new Error('Unauthorized');
          }
          if (!res.ok) {
            throw new Error(\`Server error: \${res.status} \${res.statusText}\`);
          }
          return res.json();
        })
        .then(data => {
          try {
            localStorage.setItem(CACHE_KEY, JSON.stringify({ data, cachedAt: Date.now() }));
          } catch (e) { /* quota exceeded — skip caching */ }
          renderResults(data);
        })
        .catch(err => {
          if (err.message !== 'Unauthorized') {
            console.error("Fetch error:", err);
            resultsSection.innerHTML = "<p style='text-align:center;'>Could not load recommendations.</p>";
          }
        });
    }`;

let newFetch = `    const apiUrl = \`/api/recommend?query=\${encodeURIComponent(query)}&duration=\${encodeURIComponent(duration)}\`;

    function fetchRecommendations(isPolling = false) {
      fetch(apiUrl, { credentials: 'include' })
        .then(res => {
          if (res.status === 401) {
            window.location.href = '/auth';
            throw new Error('Unauthorized');
          }
          if (!res.ok) {
            throw new Error(\`Server error: \${res.status} \${res.statusText}\`);
          }
          return res.json();
        })
        .then(data => {
          try {
            localStorage.setItem(CACHE_KEY, JSON.stringify({ data, cachedAt: Date.now() }));
          } catch (e) { /* quota exceeded — skip caching */ }

          renderResults(data, isPolling);

          // If we have fewer than 10 results, a background ingestion task is likely running.
          // We should poll for updates.
          if (!isPolling && (!data.results || data.results.length < 10)) {
            let pollCount = 0;
            const maxPolls = 10; // Poll for about 30 seconds

            // Add a temporary UI indicator
            const indicator = document.createElement("div");
            indicator.id = "pollingIndicator";
            indicator.style.textAlign = "center";
            indicator.style.padding = "20px";
            indicator.style.color = "#666";
            indicator.innerHTML = "<em>Searching the web for fresh videos...</em>";
            resultsSection.parentNode.insertBefore(indicator, resultsSection.nextSibling);

            const intervalId = setInterval(() => {
              pollCount++;
              fetch(apiUrl, { credentials: 'include' })
                .then(res => res.ok ? res.json() : null)
                .then(newData => {
                  if (newData && newData.results) {
                    // Update cache
                    try {
                       localStorage.setItem(CACHE_KEY, JSON.stringify({ data: newData, cachedAt: Date.now() }));
                    } catch(e){}

                    // Re-render
                    renderResults(newData, true);

                    // If we found enough results, stop polling
                    if (newData.results.length >= 10 || pollCount >= maxPolls) {
                      clearInterval(intervalId);
                      const ind = document.getElementById("pollingIndicator");
                      if (ind) ind.remove();
                    }
                  }
                })
                .catch(() => {
                  // Silently handle polling errors to avoid interrupting UX
                  if (pollCount >= maxPolls) {
                    clearInterval(intervalId);
                    const ind = document.getElementById("pollingIndicator");
                    if (ind) ind.remove();
                  }
                });
            }, 3000);
          }
        })
        .catch(err => {
          if (err.message !== 'Unauthorized') {
            console.error("Fetch error:", err);
            resultsSection.innerHTML = "<p style='text-align:center;'>Could not load recommendations.</p>";
          }
        });
    }

    if (!cacheHit) {
      fetchRecommendations(false);
    } else {
      // Even on cache hit, if we have few results, we might want to poll just in case
      // the background ingestion from a previous request just finished.
      // But to be safe and avoid unnecessary API calls on cached fast-loads,
      // we only fetch if the cached results are empty.
      const raw = localStorage.getItem(CACHE_KEY);
      if (raw) {
         try {
            const entry = JSON.parse(raw);
            if (!entry.data || !entry.data.results || entry.data.results.length < 5) {
               fetchRecommendations(false);
            }
         } catch(e) {}
      }
    }`;

code = code.replace(oldFetch, newFetch);

fs.writeFileSync('frontend/results.js', code);

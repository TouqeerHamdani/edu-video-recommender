import re

with open('frontend/results.js', 'r') as f:
    content = f.read()

# Replace renderResults manually using regex
new_render = """  function renderResults(data, isPolling = false) {
        if (!isPolling) {
          resultsSection.innerHTML = "";
        } else {
          // Re-render completely for simplicity
          resultsSection.innerHTML = "";
        }

        if (!data.results || data.results.length === 0) {
          if (!isPolling) {
             resultsSection.innerHTML = "<p style='text-align:center;'>No results found in database. Searching the web...</p>";
          }
          return;
        }

        data.results.forEach(video => {"""

content = re.sub(
    r'  function renderResults\(data\) \{\s*resultsSection\.innerHTML = "";\s*if \(!data\.results \|\| data\.results\.length === 0\) \{\s*resultsSection\.innerHTML = "<p style=\'text-align:center;\'>No results found\.</p>";\s*return;\s*\}\s*data\.results\.forEach\(video => \{',
    new_render,
    content
)

# Find the block starting with "if (!cacheHit) {" and ending before "} })();"
start_idx = content.find("if (!cacheHit) {")
end_idx = content.rfind("  }\n})();")

if start_idx != -1 and end_idx != -1:
    old_fetch_block = content[start_idx:end_idx]

    new_fetch_block = """const apiUrl = `/api/recommend?query=${encodeURIComponent(query)}&duration=${encodeURIComponent(duration)}`;

    function fetchRecommendations(isPolling = false) {
      if (!isPolling) {
        // Show loading state initially if not polling
        resultsSection.innerHTML = "<p style='text-align:center;'>Loading recommendations...</p>";
      }

      fetch(apiUrl, { credentials: 'include' })
        .then(res => {
          if (res.status === 401) {
            window.location.href = '/auth';
            throw new Error('Unauthorized');
          }
          if (!res.ok) {
            throw new Error(`Server error: ${res.status} ${res.statusText}`);
          }
          return res.json();
        })
        .then(data => {
          try {
            localStorage.setItem(CACHE_KEY, JSON.stringify({ data, cachedAt: Date.now() }));
          } catch (e) { /* quota exceeded — skip caching */ }

          renderResults(data, isPolling);

          // If we have fewer than 10 results, a background ingestion task is running.
          // We should poll for updates.
          if (!isPolling && (!data.results || data.results.length < 10)) {
            let pollCount = 0;
            const maxPolls = 10; // Poll for about 30 seconds

            // Add a temporary UI indicator
            let indicator = document.getElementById("pollingIndicator");
            if (!indicator) {
                indicator = document.createElement("div");
                indicator.id = "pollingIndicator";
                indicator.style.textAlign = "center";
                indicator.style.padding = "20px";
                indicator.style.color = "#888";
                indicator.innerHTML = "<em>Searching the web for fresh videos...</em>";
                resultsSection.parentNode.insertBefore(indicator, resultsSection.nextSibling);
            }

            const intervalId = setInterval(() => {
              pollCount++;
              fetch(apiUrl, { credentials: 'include' })
                .then(res => res.ok ? res.json() : null)
                .then(newData => {
                  if (newData && newData.results) {
                    try {
                       localStorage.setItem(CACHE_KEY, JSON.stringify({ data: newData, cachedAt: Date.now() }));
                    } catch(e){}

                    renderResults(newData, true);

                    // Stop polling if we found enough results or max polls reached
                    if (newData.results.length >= 10 || pollCount >= maxPolls) {
                      clearInterval(intervalId);
                      const ind = document.getElementById("pollingIndicator");
                      if (ind) ind.remove();
                    }
                  }
                })
                .catch(() => {
                  // Ignore polling errors
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
      // Check if cache needs a background refresh due to missing results
      try {
        const raw = localStorage.getItem(CACHE_KEY);
        if (raw) {
           const entry = JSON.parse(raw);
           if (!entry.data || !entry.data.results || entry.data.results.length < 5) {
              fetchRecommendations(true);
           }
        }
      } catch(e) {}
    }"""

    content = content[:start_idx] + new_fetch_block + "\n" + content[end_idx:]

with open('frontend/results.js', 'w') as f:
    f.write(content)

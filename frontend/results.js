(function () {
  function getQueryParam(param) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(param);
  }

  // Extract YouTube video ID from various URL formats
  function extractYouTubeId(url) {
    if (!url) return undefined;
    try {
      const parsed = new URL(url);
      // Standard: youtube.com/watch?v=ID
      if (parsed.searchParams.has("v")) {
        return parsed.searchParams.get("v");
      }
      // Short: youtu.be/ID
      if (parsed.hostname === "youtu.be") {
        return parsed.pathname.slice(1).split("/")[0] || undefined;
      }
      // Embed: youtube.com/embed/ID
      const embedMatch = parsed.pathname.match(/\/embed\/([^/?]+)/);
      if (embedMatch) return embedMatch[1];
    } catch (e) {
      // Not a valid URL
    }
    return undefined;
  }

  const query = getQueryParam("query");
  const duration = getQueryParam("duration") || "any";
  const resultsSection = document.getElementById("results");
  if (!resultsSection) {
    console.warn("Results section element not found");
    return;
  }

  // Populate search input with current query
  const searchInput = document.getElementById("searchInput");
  if (searchInput && query) {
    searchInput.value = query;
  }

  // Client-side cache: localStorage persists across tab closes and browser restarts.
  // Each entry wraps results with a timestamp; entries older than TTL_MS are treated as misses.
  const CACHE_KEY = `rec:${query}:${duration}`;
  const TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

  function renderResults(data, isPolling = false) {
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

        data.results.forEach(video => {
          const videoId = video.video_id || extractYouTubeId(video.link) || "";
          const card = document.createElement("a");
          card.className = "video-card";
          card.href = `/video?videoId=${encodeURIComponent(videoId)}&title=${encodeURIComponent(video.title)}&channel=${encodeURIComponent(video.channel)}`;
          card.style.textDecoration = "none";

          // Build card content safely (no innerHTML) to prevent XSS
          const img = document.createElement("img");
          img.src = video.thumbnail || '';
          img.alt = "Thumbnail";
          img.onerror = function () { this.src = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" fill="%2313131b"><rect width="480" height="360"/><text x="240" y="180" text-anchor="middle" dominant-baseline="central" fill="%2352525b" font-family="sans-serif" font-size="16">No Thumbnail</text></svg>'); };
          card.appendChild(img);

          const info = document.createElement("div");
          info.className = "info";
          const h3 = document.createElement("h3");
          h3.textContent = video.title;
          const p = document.createElement("p");
          p.textContent = video.channel;
          info.appendChild(h3);
          info.appendChild(p);
          card.appendChild(info);

          // Log click interaction (best-effort, don't block navigation)
          card.addEventListener("click", () => {
            if (video.video_id) {
              fetch('/api/interactions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                  video_id: video.video_id,
                  interaction_type: 'click'
                })
              }).catch(() => { });
            }
          });

          resultsSection.appendChild(card);
        });
  }

  if (!query) {
    resultsSection.innerHTML = "<p style='text-align:center;'>No query provided.</p>";
  } else {
    // Check client-side cache first — avoids full round-trip for repeated queries
    let cacheHit = false;
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (raw) {
        const entry = JSON.parse(raw);
        if (entry && entry.cachedAt && (Date.now() - entry.cachedAt < TTL_MS)) {
          renderResults(entry.data);
          cacheHit = true;
        } else {
          localStorage.removeItem(CACHE_KEY); // expired — evict and fall through
        }
      }
    } catch (e) {
      localStorage.removeItem(CACHE_KEY); // corrupted entry — fall through to fetch
    }

    const apiUrl = `/api/recommend?query=${encodeURIComponent(query)}&duration=${encodeURIComponent(duration)}`;

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
    }
  }
})();

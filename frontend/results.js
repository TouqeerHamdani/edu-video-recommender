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

  if (!query) {
    resultsSection.innerHTML = "<p style='text-align:center;'>No query provided.</p>";
  } else {
    // Build API URL with query and duration
    const apiUrl = `/api/recommend?query=${encodeURIComponent(query)}&duration=${encodeURIComponent(duration)}`;

    fetch(apiUrl, { credentials: 'include' })
      .then(res => {
        if (res.status === 401) {
          // Not logged in — redirect to auth
          window.location.href = '/auth';
          throw new Error('Unauthorized');
        }
        if (!res.ok) {
          throw new Error(`Server error: ${res.status} ${res.statusText}`);
        }
        return res.json();
      })
      .then(data => {
        resultsSection.innerHTML = "";

        if (!data.results || data.results.length === 0) {
          resultsSection.innerHTML = "<p style='text-align:center;'>No results found.</p>";
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
      })
      .catch(err => {
        if (err.message !== 'Unauthorized') {
          console.error("Fetch error:", err);
          resultsSection.innerHTML = "<p style='text-align:center;'>Could not load recommendations.</p>";
        }
      });
  }
})();

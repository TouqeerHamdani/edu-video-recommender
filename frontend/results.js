function getQueryParam(param) {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(param);
}

const query = getQueryParam("query");
const user = getQueryParam("user") || "guest";

const resultsSection = document.getElementById("results");

if (!query) {
  resultsSection.innerHTML = "<p>No query provided.</p>";
} else {
  fetch(`/api/recommend?query=${encodeURIComponent(query)}&user=${user}`)
    .then(res => res.json())
    .then(data => {
      resultsSection.innerHTML = "";
      data.results.forEach(video => {
        const videoId = video.link.split("v=")[1];
        const card = document.createElement("a");
        card.className = "video-card";
        card.href = `/video?videoId=${videoId}&title=${encodeURIComponent(video.title)}&channel=${encodeURIComponent(video.channel)}`;
        card.style.textDecoration = "none";
        card.innerHTML = `
          <img src="${video.thumbnail}" alt="Thumbnail">
          <div class="info">
            <h3>${video.title}</h3>
            <p>${video.channel}</p>
          </div>
        `;
        resultsSection.appendChild(card);
      });
    })
    .catch(err => {
      console.error("Fetch error:", err);
      resultsSection.innerHTML = "<p>Could not load recommendations.</p>";
    });
}

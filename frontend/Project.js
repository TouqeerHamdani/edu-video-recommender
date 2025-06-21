document.getElementById("searchBtn").addEventListener("click", () => {
  const query = document.getElementById("searchInput").value.trim();
  if (!query) {
    alert("Please enter a search query.");
    return;
  }

  // Redirect to results.html with query
  window.location.href = `results.html?query=${encodeURIComponent(query)}&user=guest`;
});

function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  sidebar.classList.toggle("active");
}

//Update the the URL with sorting parameters while preserving other parameters
function updateUrlWithSorting(value) {
  const params = new URLSearchParams(window.location.search);

  params.set("order", value);

  //Keeps current page number or default to 1
  const page = params.get("page") || "1";
  params.set("page", page);

  window.location.href = `/?${params.toString()}`;
}

//DOM has to be loaded for execution
document.addEventListener("DOMContentLoaded", () => {
  const applyFiltersButton = document.getElementById("apply-filters");

  applyFiltersButton.addEventListener("click", () => {
    //Collect values for all checkboxes
    const selectedFilters = Array.from(
      document.querySelectorAll(".filter-checkbox:checked")
    ).map((checkbox) => checkbox.value);

    const params = new URLSearchParams(window.location.search);

    //Keep current category ifit exists
    const category = params.get("category");
    if (category) {
      params.set("category", category);
    }

    params.delete("filter");
    selectedFilters.forEach((filter) => params.append("filter", filter));

    window.location.href = `/?${params.toString()}`;
  });
});

//To keep track of current product id
let currentProductId = null;

//Show price history for a specific product
function showPriceHistory(productId) {
  console.log("showPriceHistory called with productId:", productId);
  currentProductId = productId;
  const modal = document.getElementById("priceHistoryModal");

  //Check if modal element exists in DOM
  if (!modal) {
    console.error("Modal element not found!");
    return;
  }
  modal.style.display = "block";
  updatePriceHistory();
}

//Fetch current product price history to display
function updatePriceHistory() {
  console.log("updatePriceHistory called for productId:", currentProductId);
  if (!currentProductId) {
    console.error("No product ID set!");
    return;
  }

  //Get the selected time frame
  const timeframe = document.getElementById("timeframeSelect").value;
  console.log("Fetching data for timeframe:", timeframe);

  document.getElementById("priceHistoryChart").innerHTML = "";

  //Fetch price history data from API
  fetch(`/api/product/${currentProductId}/price_history/${timeframe}`)
    .then((response) => {
      console.log("Response status:", response.status);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      console.log("Received data:", data);

      //Mesage if there is no historical data for product
      if (!data || data.length === 0) {
        console.log("Atvainojamies! Cenu vēsture nav pieejama.");
        document.getElementById("priceHistoryChart").innerHTML =
          "Atvainojamies! Cenu vēsture nav pieejama.";
        return;
      }

      //Configure data value points on chart
      const trace = {
        x: data.map((item) => item.date),
        y: data.map((item) => item.price),
        type: "scatter",
        mode: "lines+markers",
        line: {
          color: "#865d36",
          width: 2,
        },
        marker: {
          color: "#ac8968",
          size: 6,
        },
      };

      //Configure chart layout
      const layout = {
        title: "Cenu vēsture",
        xaxis: {
          title: "Datums",
          tickangle: -45,
        },
        yaxis: {
          title: "Cena (€)",
          tickformat: "€.2f",
        },
        paper_bgcolor: "#f9f9f9",
        plot_bgcolor: "#f9f9f9",
        margin: {
          l: 50,
          r: 20,
          t: 40,
          b: 90,
        },
      };

      //Create chart with Plotly
      Plotly.newPlot("priceHistoryChart", [trace], layout);
    })
    .catch((error) => {
      console.error("Error:", error);
      document.getElementById("priceHistoryChart").innerHTML =
        "Kļūda cenas vēstures ielādē";
    });
}

//For closing price history view
function closeModal() {
  console.log("closeModal called");
  const modal = document.getElementById("priceHistoryModal");
  if (!modal) {
    console.error("Modal element not found!");
    return;
  }
  modal.style.display = "none";
}

//Also close ifclicked outside of modal content
window.onclick = function (event) {
  const modal = document.getElementById("priceHistoryModal");
  if (event.target === modal) {
    modal.style.display = "none";
  }
};

// SmartShelf Chart.js Initializer
function initDashboardCharts(chartData) {
  if (!chartData || typeof Chart === 'undefined') return;

  // 1. Monthly Loans Trend Line Chart
  const monthlyCanvas = document.getElementById('monthlyLoansChart');
  if (monthlyCanvas && chartData.monthly) {
    new Chart(monthlyCanvas, {
      type: 'line',
      data: {
        labels: chartData.monthly.labels,
        datasets: [{
          label: 'Book Loans',
          data: chartData.monthly.counts,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37, 99, 235, 0.1)',
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointBackgroundColor: '#1d4ed8',
          pointRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0 }
          }
        }
      }
    });
  }

  // 2. Category Distribution Bar Chart
  const categoryCanvas = document.getElementById('categoryDistributionChart');
  if (categoryCanvas && chartData.categories) {
    new Chart(categoryCanvas, {
      type: 'bar',
      data: {
        labels: chartData.categories.labels,
        datasets: [{
          label: 'Titles in Category',
          data: chartData.categories.counts,
          backgroundColor: '#3b82f6',
          borderRadius: 6
        }, {
          label: 'Total Borrows',
          data: chartData.categories.loans,
          backgroundColor: '#0ea5e9',
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top' }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0 }
          }
        }
      }
    });
  }

  // 3. Loan Status Doughnut Chart
  const statusCanvas = document.getElementById('loanStatusChart');
  if (statusCanvas && chartData.status_distribution) {
    const s = chartData.status_distribution;
    new Chart(statusCanvas, {
      type: 'doughnut',
      data: {
        labels: ['Returned', 'Active (On Time)', 'Overdue'],
        datasets: [{
          data: [s.returned, s.active, s.overdue],
          backgroundColor: ['#10b981', '#3b82f6', '#ef4444'],
          borderWidth: 2,
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' }
        },
        cutout: '70%'
      }
    });
  }
}

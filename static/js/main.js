document.addEventListener('DOMContentLoaded', () => {
  // 1. Auto-dismiss flash alert toasts
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(alert => {
    setTimeout(() => {
      try {
        const bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
      } catch (e) {}
    }, 6000);
  });

  // 2. Data-confirm confirmation modal / prompt for destructive operations
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', (e) => {
      const msg = el.getAttribute('data-confirm') || 'Are you sure you want to proceed?';
      if (!confirm(msg)) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    });
  });

  // 3. Mobile sidebar toggle
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebar = document.querySelector('.sidebar');
  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('show');
    });
  }

  // 4. Quick Accession ID copy-lookup for Issue/Return forms
  const accessionInputs = document.querySelectorAll('.accession-lookup-input');
  accessionInputs.forEach(input => {
    const feedbackBox = document.getElementById(input.dataset.previewTarget);
    if (!feedbackBox) return;

    let debounceTimer;
    input.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      const accId = input.value.trim().toUpperCase();
      if (accId.length < 3) {
        feedbackBox.innerHTML = '';
        return;
      }

      debounceTimer = setTimeout(() => {
        fetch(`/api/copy-lookup/${encodeURIComponent(accId)}`)
          .then(res => res.json())
          .then(data => {
            if (data.success && data.copy) {
              const c = data.copy;
              const statusBadge = c.status === 'available'
                ? '<span class="badge bg-success">Available</span>'
                : c.status === 'borrowed'
                ? '<span class="badge bg-danger">Borrowed</span>'
                : `<span class="badge bg-warning">${c.status}</span>`;

              feedbackBox.innerHTML = `
                <div class="card p-2 border-0 bg-light mt-2 small">
                  <div><strong>Title:</strong> ${c.title}</div>
                  <div><strong>Author:</strong> ${c.author} | <strong>Rack:</strong> ${c.location_rack || 'N/A'}</div>
                  <div><strong>Status:</strong> ${statusBadge} | <strong>Condition:</strong> ${c.condition}</div>
                  ${c.active_borrower ? `<div class="text-danger mt-1"><strong>Current Borrower:</strong> ${c.active_borrower.name} (Due: ${c.active_borrower.due_date})</div>` : ''}
                </div>
              `;
            } else {
              feedbackBox.innerHTML = `
                <div class="text-danger small mt-2">
                  <i class="bi bi-exclamation-circle me-1"></i> ${data.message || 'Copy not found'}
                </div>
              `;
            }
          })
          .catch(() => {
            feedbackBox.innerHTML = '';
          });
      }, 350);
    });
  });

  // 5. Member Lookup Autocomplete / Verification for Issue form
  const memberEmailInput = document.getElementById('memberLookupInput');
  const memberPreview = document.getElementById('memberLookupPreview');
  if (memberEmailInput && memberPreview) {
    let debounceTimer;
    memberEmailInput.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      const query = memberEmailInput.value.trim();
      if (query.length < 2) {
        memberPreview.innerHTML = '';
        return;
      }

      debounceTimer = setTimeout(() => {
        fetch(`/api/member-lookup/${encodeURIComponent(query)}`)
          .then(res => res.json())
          .then(data => {
            if (data.success && data.member) {
              const m = data.member;
              const fineBadge = m.unpaid_fines > 0
                ? `<span class="badge bg-danger">$${m.unpaid_fines.toFixed(2)} Unpaid Fines</span>`
                : '<span class="badge bg-success">No Fines</span>';

              memberPreview.innerHTML = `
                <div class="card p-2 border-0 bg-light mt-2 small">
                  <div><strong>Member:</strong> ${m.name} (${m.email})</div>
                  <div><strong>Active Loans:</strong> ${m.active_loans} / ${m.max_loans} allowed</div>
                  <div><strong>Status:</strong> ${m.status === 'active' ? '<span class="badge bg-success">Active</span>' : '<span class="badge bg-danger">Suspended</span>'} | ${fineBadge}</div>
                </div>
              `;
            } else {
              memberPreview.innerHTML = `
                <div class="text-muted small mt-2">
                  <i class="bi bi-info-circle me-1"></i> Member not found or search query too short.
                </div>
              `;
            }
          })
          .catch(() => {
            memberPreview.innerHTML = '';
          });
      }, 350);
    });
  }
});

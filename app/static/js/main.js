document.addEventListener('DOMContentLoaded', () => {
    // Hub Details Toggle
    const toggleSwitches = document.querySelectorAll('.hub-toggle');
    
    toggleSwitches.forEach(toggle => {
        toggle.addEventListener('change', function() {
            const targetId = this.getAttribute('data-target');
            const detailsElement = document.getElementById(targetId);
            
            if (this.checked) {
                detailsElement.classList.add('open');
            } else {
                detailsElement.classList.remove('open');
            }
        });
    });

    // Button Click Interactivity
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(btn => {
        btn.addEventListener('mousedown', () => {
            btn.style.transform = 'scale(0.95)';
        });
        btn.addEventListener('mouseup', () => {
            btn.style.transform = 'scale(1)';
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.transform = 'scale(1)';
        });
    });

    // Mock Functionality for Dashboard Buttons
    window.handleOrderStock = () => {
        alert("Secure Reorder Request Sent! We are contacting the supplier for fresh stock.");
    };

    window.handleViewVendors = () => {
        alert("Redirecting to Supplier Management Hub...");
    };

    // Mobile Sidebar Toggle (For responsiveness)
    const menuBtn = document.getElementById('menuBtn');
    const sidebar = document.querySelector('.sidebar');
    
    if (menuBtn && sidebar) {
        menuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
});

/**
 * Right-side toast notification system.
 * Provides showToast(message, type) where type is 'success', 'error', 'warning', or 'info'.
 */

(function () {
    // Inject toast container styles once
    const style = document.createElement('style');
    style.textContent = `
        #toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 99999;
            display: flex;
            flex-direction: column;
            gap: 10px;
            pointer-events: none;
        }

        .toast-notification {
            pointer-events: auto;
            min-width: 280px;
            max-width: 400px;
            padding: 14px 20px;
            border-radius: 8px;
            font-family: 'Poppins', 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            color: #fff;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            gap: 10px;
            transform: translateX(120%);
            opacity: 0;
            transition: transform 0.4s ease, opacity 0.4s ease;
        }

        .toast-notification.show {
            transform: translateX(0);
            opacity: 1;
        }

        .toast-notification.hide {
            transform: translateX(120%);
            opacity: 0;
        }

        .toast-notification.toast-success {
            background: linear-gradient(135deg, #28a745, #218838);
        }

        .toast-notification.toast-error {
            background: linear-gradient(135deg, #dc3545, #c82333);
        }

        .toast-notification.toast-warning {
            background: linear-gradient(135deg, #ffc107, #e0a800);
            color: #333;
        }

        .toast-notification.toast-info {
            background: linear-gradient(135deg, #17a2b8, #138496);
        }

        .toast-icon {
            font-size: 18px;
            flex-shrink: 0;
        }

        .toast-message {
            flex: 1;
            line-height: 1.4;
        }

        .toast-close {
            cursor: pointer;
            font-size: 18px;
            flex-shrink: 0;
            opacity: 0.8;
            transition: opacity 0.2s;
            background: none;
            border: none;
            color: inherit;
            padding: 0;
            line-height: 1;
        }

        .toast-close:hover {
            opacity: 1;
        }
    `;
    document.head.appendChild(style);

    // Create container
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }

    const icons = {
        success: '\u2714',
        error: '\u2716',
        warning: '\u26A0',
        info: '\u2139'
    };

    /**
     * Show a right-side toast notification.
     * @param {string} message - The message to display.
     * @param {string} [type='info'] - One of 'success', 'error', 'warning', 'info'.
     * @param {number} [duration=4000] - Time in ms before auto-dismiss.
     */
    window.showToast = function (message, type, duration) {
        type = type || 'info';
        duration = duration || 4000;

        // Ensure container is in the DOM (for pages that load this script early)
        if (!document.getElementById('toast-container')) {
            document.body.appendChild(container);
        }

        var toast = document.createElement('div');
        toast.className = 'toast-notification toast-' + type;

        toast.innerHTML =
            '<span class="toast-icon">' + (icons[type] || icons.info) + '</span>' +
            '<span class="toast-message">' + message + '</span>' +
            '<button class="toast-close" aria-label="Close">&times;</button>';

        container.appendChild(toast);

        // Trigger slide-in animation
        requestAnimationFrame(function () {
            toast.classList.add('show');
        });

        function dismiss() {
            toast.classList.remove('show');
            toast.classList.add('hide');
            setTimeout(function () {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 400);
        }

        // Close button
        toast.querySelector('.toast-close').addEventListener('click', dismiss);

        // Auto-dismiss
        setTimeout(dismiss, duration);
    };
})();

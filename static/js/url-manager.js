/**
 * URL Management Modal System
 * Handles editing, deactivating, and deleting URLs
 */

class UrlManager {
    constructor() {
        this.currentUrlData = null;
        this.hostUrl = window.dashboardConfig?.hostUrl || '';

        // Modal elements
        this.modal = document.getElementById('url-management-modal');
        this.deleteModal = document.getElementById('delete-confirmation-modal');
        this.form = document.getElementById('url-edit-form');

        // Form elements
        this.aliasInput = document.getElementById('edit-alias');
        this.longUrlInput = document.getElementById('edit-long-url');
        this.passwordInput = document.getElementById('edit-password');
        this.removePasswordCheckbox = document.getElementById('remove-password-checkbox');
        this.passwordStatus = document.getElementById('password-status');
        this.privateStatsCheckbox = document.getElementById('edit-private-stats');
        this.maxClicksInput = document.getElementById('edit-max-clicks');
        this.expireAfterInput = document.getElementById('edit-expire-after');
        this.blockBotsCheckbox = document.getElementById('edit-block-bots');

        // Buttons
        this.deactivateBtn = document.getElementById('btn-deactivate');
        this.deleteBtn = document.getElementById('btn-delete-url');
        this.saveBtn = document.getElementById('btn-save');

        // Delete confirmation elements
        this.deleteUrlPreview = document.getElementById('delete-url-preview');
        this.deleteConfirmationInput = document.getElementById('delete-confirmation-input');
        this.cancelDeleteBtn = document.getElementById('btn-cancel-delete');
        this.confirmDeleteBtn = document.getElementById('btn-confirm-delete');

        this.init();
    }

    init() {
        // Tab switching
        this.initTabs();

        // Modal event listeners
        this.modal?.querySelector('.modal-close')?.addEventListener('click', () => this.closeModal());
        this.modal?.querySelector('.modal-backdrop')?.addEventListener('click', () => this.closeModal());

        // Action buttons
        this.deactivateBtn?.addEventListener('click', () => this.deactivateUrl());
        this.deleteBtn?.addEventListener('click', () => this.showDeleteConfirmation());
        this.saveBtn?.addEventListener('click', () => this.saveChanges());

        // Password checkbox logic
        this.removePasswordCheckbox?.addEventListener('change', () => this.handlePasswordCheckboxChange());

        // Delete confirmation modal
        this.deleteModal?.querySelector('.modal-close')?.addEventListener('click', () => this.closeDeleteModal());
        this.deleteModal?.querySelector('.modal-backdrop')?.addEventListener('click', () => this.closeDeleteModal());
        this.cancelDeleteBtn?.addEventListener('click', () => this.closeDeleteModal());
        this.confirmDeleteBtn?.addEventListener('click', () => this.confirmDelete());

        // Delete confirmation input validation
        this.deleteConfirmationInput?.addEventListener('input', () => this.validateDeleteInput());

        // Form submission
        this.form?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveChanges();
        });

        // ESC key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (this.deleteModal?.classList.contains('active')) {
                    this.closeDeleteModal();
                } else if (this.modal?.classList.contains('active')) {
                    this.closeModal();
                }
            }
        });

        // Attach to row action buttons
        this.attachRowListeners();
    }

    initTabs() {
        const tabs = document.querySelectorAll('.tab');
        const tabContents = document.querySelectorAll('.tab-content');
        const tabsContainer = document.querySelector('.tabs');

        tabs.forEach((tab, index) => {
            tab.addEventListener('click', () => {
                const targetTab = tab.getAttribute('data-tab');

                // Update tab indicator position
                if (tabsContainer) {
                    tabsContainer.setAttribute('data-active', index.toString());
                }

                // Update tab states
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                // Update content states - simple show/hide
                tabContents.forEach(content => {
                    content.classList.remove('active');
                    if (content.getAttribute('data-tab') === targetTab) {
                        content.classList.add('active');
                    }
                });
            });
        });
    }

    attachRowListeners() {
        // Use event delegation for dynamically added rows
        document.addEventListener('click', (e) => {
            const clickableRow = e.target.closest('.clickable-row');

            if (clickableRow) {
                // Prevent opening modal if clicking on links
                if (e.target.closest('a')) {
                    return;
                }

                const urlDataStr = clickableRow.getAttribute('data-url-data');
                if (urlDataStr) {
                    try {
                        const urlData = JSON.parse(urlDataStr);
                        this.editUrl(urlData);
                    } catch (error) {
                        console.error('Error parsing URL data:', error);
                    }
                }
            }
        });
    }



    editUrl(urlData) {
        this.currentUrlData = urlData;
        this.populateForm(urlData);
        this.showModal();
    }

    populateForm(urlData) {
        // Basic tab
        if (this.aliasInput) this.aliasInput.value = urlData.alias || '';
        if (this.longUrlInput) this.longUrlInput.value = urlData.long_url || '';

        // Security tab - Password handling
        if (this.passwordInput) this.passwordInput.value = ''; // Never populate actual password

        // Setup password checkbox and status
        if (this.removePasswordCheckbox) {
            this.removePasswordCheckbox.checked = false;

            if (urlData.password_set) {
                // URL has password - enable checkbox, show status
                this.removePasswordCheckbox.disabled = false;
                if (this.passwordStatus) this.passwordStatus.textContent = 'Password is currently set';
            } else {
                // URL has no password - disable checkbox, show status
                this.removePasswordCheckbox.disabled = true;
                if (this.passwordStatus) this.passwordStatus.textContent = 'No password set';
            }
        }

        if (this.privateStatsCheckbox) this.privateStatsCheckbox.checked = urlData.private_stats || false;

        // Advanced tab
        if (this.maxClicksInput) this.maxClicksInput.value = urlData.max_clicks || '';
        if (this.expireAfterInput) {
            if (urlData.expire_after) {
                const date = new Date(urlData.expire_after * 1000);
                this.expireAfterInput.value = date.toISOString().slice(0, 16);
            } else {
                this.expireAfterInput.value = '';
            }
        }
        if (this.blockBotsCheckbox) this.blockBotsCheckbox.checked = urlData.block_bots || false;

        // Update deactivate button based on current status
        this.updateDeactivateButton(urlData.status);
    }

    handlePasswordCheckboxChange() {
        if (!this.removePasswordCheckbox || !this.passwordInput) return;

        if (this.removePasswordCheckbox.checked) {
            // User wants to remove password - disable input
            this.passwordInput.disabled = true;
            this.passwordInput.value = '';
            this.passwordInput.placeholder = 'Password will be removed';
            if (this.passwordStatus) this.passwordStatus.textContent = 'Password will be removed';
        } else {
            // User unchecked - enable input
            this.passwordInput.disabled = false;
            this.passwordInput.placeholder = 'Enter new password';
            if (this.passwordStatus) {
                const hasPassword = this.currentUrlData?.password_set;
                this.passwordStatus.textContent = hasPassword ? 'Password is currently set' : 'No password set';
            }
        }
    }

    updateDeactivateButton(status) {
        if (this.deactivateBtn) {
            if (status === 'ACTIVE') {
                this.deactivateBtn.innerHTML = '<i class="ti ti-player-pause"></i><span>Deactivate</span>';
                this.deactivateBtn.className = 'btn btn-warning';
            } else {
                this.deactivateBtn.innerHTML = '<i class="ti ti-player-play"></i><span>Activate</span>';
                this.deactivateBtn.className = 'btn btn-success';
            }
        }
    }

    showModal() {
        if (this.modal) {
            this.modal.classList.add('active');
            document.body.style.overflow = 'hidden';

            // Initialize tab indicator to first tab
            const tabsContainer = this.modal.querySelector('.tabs');
            if (tabsContainer) {
                tabsContainer.setAttribute('data-active', '0');
            }

            // Focus first input
            setTimeout(() => {
                this.aliasInput?.focus();
            }, 400);
        }
    }

    closeModal() {
        if (this.modal) {
            this.modal.classList.remove('active');
            document.body.style.overflow = '';
            this.currentUrlData = null;
        }
    }

    async saveChanges() {
        if (!this.currentUrlData) return;

        const updateData = {};
        let hasChanges = false;

        // Check alias changes
        const currentAlias = this.aliasInput?.value?.trim();
        if (currentAlias && currentAlias !== this.currentUrlData.alias) {
            updateData.alias = currentAlias;
            hasChanges = true;
        }

        // Check long_url changes
        const currentLongUrl = this.longUrlInput?.value?.trim();
        if (currentLongUrl && currentLongUrl !== this.currentUrlData.long_url) {
            updateData.long_url = currentLongUrl;
            hasChanges = true;
        }

        // Check password changes
        if (this.removePasswordCheckbox?.checked) {
            // User explicitly wants to remove password
            updateData.password = null;
            hasChanges = true;
        } else {
            // Check if new password was entered
            const currentPassword = this.passwordInput?.value?.trim();
            if (currentPassword && currentPassword !== '') {
                // New password entered
                updateData.password = currentPassword;
                hasChanges = true;
            }
            // If password field is empty and checkbox not checked = no change (keep existing)
        }

        // Check max_clicks changes (including removal)
        const currentMaxClicks = this.maxClicksInput?.value?.trim();
        const originalMaxClicks = this.currentUrlData.max_clicks;
        if (currentMaxClicks === '' && originalMaxClicks) {
            // Remove max_clicks
            updateData.max_clicks = null;
            hasChanges = true;
        } else if (currentMaxClicks && parseInt(currentMaxClicks) !== originalMaxClicks) {
            // Update max_clicks
            updateData.max_clicks = parseInt(currentMaxClicks);
            hasChanges = true;
        }

        // Check expire_after changes (including removal)
        const currentExpireAfter = this.expireAfterInput?.value;
        const originalExpireAfter = this.currentUrlData.expire_after;
        if (currentExpireAfter === '' && originalExpireAfter) {
            // Remove expiration
            updateData.expire_after = null;
            hasChanges = true;
        } else if (currentExpireAfter) {
            const newExpireTs = Math.floor(new Date(currentExpireAfter).getTime() / 1000);
            if (newExpireTs !== originalExpireAfter) {
                updateData.expire_after = newExpireTs;
                hasChanges = true;
            }
        }

        // Check private_stats changes
        const currentPrivateStats = this.privateStatsCheckbox?.checked || false;
        if (currentPrivateStats !== this.currentUrlData.private_stats) {
            updateData.private_stats = currentPrivateStats;
            hasChanges = true;
        }

        // Check block_bots changes
        const currentBlockBots = this.blockBotsCheckbox?.checked || false;
        if (currentBlockBots !== this.currentUrlData.block_bots) {
            updateData.block_bots = currentBlockBots;
            hasChanges = true;
        }

        // If no changes detected, show message and return
        if (!hasChanges) {
            this.showNotification('No changes detected', 'info');
            return;
        }

        try {
            this.saveBtn.disabled = true;
            this.saveBtn.innerHTML = '<i class="ti ti-loader-2"></i><span>Saving...</span>';

            // Debug: log what we're sending
            console.log('Sending update data:', updateData);

            const response = await this.apiCall(`/api/v1/urls/${this.getUrlId()}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(updateData)
            });

            if (response.ok) {
                const responseData = await response.json();

                // Update current data with the response
                this.currentUrlData = { ...this.currentUrlData, ...responseData };

                // Update password UI based on changes
                if (this.removePasswordCheckbox?.checked) {
                    // Password was removed
                    this.currentUrlData.password_set = false;
                    if (this.passwordStatus) this.passwordStatus.textContent = 'No password set';
                    if (this.removePasswordCheckbox) {
                        this.removePasswordCheckbox.checked = false;
                        this.removePasswordCheckbox.disabled = true;
                    }
                    if (this.passwordInput) {
                        this.passwordInput.disabled = false;
                        this.passwordInput.placeholder = 'Enter new password';
                    }
                } else if (updateData.password) {
                    // Password was set/changed
                    this.currentUrlData.password_set = true;
                    if (this.passwordStatus) this.passwordStatus.textContent = 'Password is currently set';
                    if (this.removePasswordCheckbox) this.removePasswordCheckbox.disabled = false;
                    if (this.passwordInput) this.passwordInput.value = ''; // Clear the field after saving
                }

                this.showNotification('URL updated successfully', 'success');

                // Update the table row with new data immediately
                this.updateTableRow(this.currentUrlData);

                // Also refresh the full list in the background
                this.refreshUrlList();
            } else {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update URL');
            }
        } catch (error) {
            console.error('Error updating URL:', error);
            this.showNotification(error.message, 'error');
        } finally {
            this.saveBtn.disabled = false;
            this.saveBtn.innerHTML = '<i class="ti ti-check"></i><span>Save Changes</span>';
        }
    }

    async deactivateUrl() {
        if (!this.currentUrlData) return;

        const currentStatus = this.currentUrlData.status || 'ACTIVE';
        const newStatus = currentStatus === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
        const originalButtonContent = this.deactivateBtn.innerHTML;

        try {
            this.deactivateBtn.disabled = true;
            this.deactivateBtn.innerHTML = '<i class="ti ti-loader-2"></i><span>Processing...</span>';

            const response = await this.apiCall(`/api/v1/urls/${this.getUrlId()}/status`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ status: newStatus })
            });

            if (response.ok) {
                // Update the current data
                this.currentUrlData.status = newStatus;

                // Update the button appearance
                this.updateDeactivateButton(newStatus);

                // Show success notification
                const action = newStatus === 'ACTIVE' ? 'activated' : 'deactivated';
                this.showNotification(`URL ${action} successfully`, 'success');

                // Update the table row immediately
                this.updateTableRow(this.currentUrlData);

                // Also refresh the full list in the background
                this.refreshUrlList();
            } else {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update URL status');
            }
        } catch (error) {
            console.error('Error updating URL status:', error);
            this.showNotification(error.message, 'error');
            // Restore original button content on error
            this.deactivateBtn.innerHTML = originalButtonContent;
        } finally {
            this.deactivateBtn.disabled = false;
        }
    }

    showDeleteConfirmation() {
        if (!this.currentUrlData) return;

        const fullUrl = `${this.hostUrl}${this.currentUrlData.alias}`;
        if (this.deleteUrlPreview) {
            this.deleteUrlPreview.textContent = fullUrl;
        }

        if (this.deleteConfirmationInput) {
            this.deleteConfirmationInput.value = '';
        }

        if (this.confirmDeleteBtn) {
            this.confirmDeleteBtn.disabled = true;
        }

        if (this.deleteModal) {
            this.deleteModal.classList.add('active');

            setTimeout(() => {
                this.deleteConfirmationInput?.focus();
            }, 100);
        }
    }

    closeDeleteModal() {
        if (this.deleteModal) {
            this.deleteModal.classList.remove('active');
        }
    }

    validateDeleteInput() {
        if (!this.deleteConfirmationInput || !this.confirmDeleteBtn || !this.currentUrlData) return;

        const inputValue = this.deleteConfirmationInput.value.trim();
        const expectedAlias = this.currentUrlData.alias;

        this.confirmDeleteBtn.disabled = inputValue !== expectedAlias;
    }

    async confirmDelete() {
        if (!this.currentUrlData) return;

        // Store the alias before making the API call (in case currentUrlData gets cleared)
        const aliasToDelete = this.currentUrlData.alias;
        console.log('About to delete URL with alias:', aliasToDelete);

        try {
            this.confirmDeleteBtn.disabled = true;
            this.confirmDeleteBtn.innerHTML = '<i class="ti ti-loader-2"></i><span>Deleting...</span>';

            const response = await this.apiCall(`/api/v1/urls/${this.getUrlId()}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.showNotification('URL deleted successfully', 'success');
                this.closeDeleteModal();
                this.closeModal();

                // Remove the row from the table immediately using the stored alias
                this.removeUrlFromTable(aliasToDelete);

                // Also refresh the full list
                this.refreshUrlList();
            } else {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to delete URL');
            }
        } catch (error) {
            console.error('Error deleting URL:', error);
            this.showNotification(error.message, 'error');
        } finally {
            this.confirmDeleteBtn.disabled = false;
            this.confirmDeleteBtn.innerHTML = '<i class="ti ti-trash"></i><span>Delete Permanently</span>';
        }
    }

    viewStats(alias) {
        // Navigate to stats page or open stats modal
        window.open(`/stats/${alias}`, '_blank');
    }

    getUrlId() {
        // Use the actual ObjectId returned by the API
        return this.currentUrlData?.id;
    }

    async apiCall(url, options = {}) {
        const defaultOptions = {
            credentials: 'same-origin',
            headers: {
                'Accept': 'application/json',
                ...options.headers
            }
        };

        return fetch(url, { ...defaultOptions, ...options });
    }

    showNotification(message, type = 'info') {
        // Create a simple notification system
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <i class="ti ti-${type === 'success' ? 'check' : type === 'error' ? 'x' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
        `;

        // Add notification styles if not present
        if (!document.getElementById('notification-styles')) {
            const styles = document.createElement('style');
            styles.id = 'notification-styles';
            styles.textContent = `
                .notification {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 10000;
                    background: rgba(255, 255, 255, 0.1);
                    backdrop-filter: blur(20px);
                    border-radius: 8px;
                    padding: 16px 20px;
                    color: white;
                    font-size: 14px;
                    font-weight: 500;
                    transform: translateX(100%);
                    transition: transform 0.3s ease;
                    border-left: 4px solid;
                }
                .notification-success { border-left-color: #10b981; }
                .notification-error { border-left-color: #ef4444; }
                .notification-info { border-left-color: #3b82f6; }
                .notification.show { transform: translateX(0); }
                .notification-content {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
            `;
            document.head.appendChild(styles);
        }

        document.body.appendChild(notification);

        // Animate in
        setTimeout(() => notification.classList.add('show'), 100);

        // Auto remove
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    removeUrlFromTable(alias) {
        if (!alias) {
            console.error('No alias provided for removal');
            return;
        }

        console.log('Removing URL from table:', alias);

        // Find and remove the table row for the deleted URL
        const rows = document.querySelectorAll('.clickable-row');
        let rowFound = false;

        rows.forEach(row => {
            const urlDataStr = row.getAttribute('data-url-data');
            if (urlDataStr) {
                try {
                    const urlData = JSON.parse(urlDataStr);
                    if (urlData.alias === alias) {
                        rowFound = true;
                        console.log('Found row to remove:', urlData);

                        // Add fade-out animation
                        row.style.transition = 'all 0.3s ease';
                        row.style.opacity = '0';
                        row.style.transform = 'translateX(-20px)';

                        // Remove after animation
                        setTimeout(() => {
                            row.remove();
                            console.log('Row removed from DOM');
                        }, 300);
                    }
                } catch (error) {
                    console.error('Error parsing URL data for removal:', error);
                }
            }
        });

        if (!rowFound) {
            console.warn('No row found with alias:', alias);
        }
    }

    updateTableRow(updatedUrlData) {
        // Find and update the table row with new data
        const rows = document.querySelectorAll('.clickable-row');
        rows.forEach(row => {
            const urlDataStr = row.getAttribute('data-url-data');
            if (urlDataStr) {
                try {
                    const urlData = JSON.parse(urlDataStr);
                    if (urlData.alias === updatedUrlData.alias || urlData.id === updatedUrlData.id) {
                        // Update the stored data
                        row.setAttribute('data-url-data', JSON.stringify(updatedUrlData));

                        // Update visible elements
                        const longUrlElement = row.querySelector('.link-long');
                        if (longUrlElement && updatedUrlData.long_url) {
                            longUrlElement.textContent = updatedUrlData.long_url;
                            longUrlElement.title = updatedUrlData.long_url;
                        }

                        const shortUrlElement = row.querySelector('.link-short');
                        if (shortUrlElement && updatedUrlData.alias) {
                            const displayHost = this.hostUrl.replace(/\/+$/, '') + '/';
                            shortUrlElement.textContent = displayHost.replace(/^https?:\/\//i, '') + updatedUrlData.alias;
                            shortUrlElement.href = '/' + updatedUrlData.alias;
                        }

                        // Update status badges
                        const activeBadge = row.querySelector('.badge-active');
                        const inactiveBadge = row.querySelector('.badge-inactive');
                        if (activeBadge && inactiveBadge) {
                            if (updatedUrlData.status === 'ACTIVE') {
                                activeBadge.style.display = 'inline-flex';
                                inactiveBadge.style.display = 'none';
                            } else if (updatedUrlData.status === 'INACTIVE') {
                                activeBadge.style.display = 'none';
                                inactiveBadge.style.display = 'inline-flex';
                            } else {
                                activeBadge.style.display = 'none';
                                inactiveBadge.style.display = 'none';
                            }
                        }

                        const passwordBadge = row.querySelector('.badge-password');
                        if (passwordBadge) {
                            passwordBadge.style.display = updatedUrlData.password_set ? 'inline-flex' : 'none';
                        }

                        const maxClicksBadge = row.querySelector('.badge-max-clicks');
                        if (maxClicksBadge) {
                            if (updatedUrlData.max_clicks) {
                                maxClicksBadge.style.display = 'inline-flex';
                                maxClicksBadge.setAttribute('data-tooltip', `Max clicks: ${updatedUrlData.max_clicks}`);
                            } else {
                                maxClicksBadge.style.display = 'none';
                            }
                        }

                        const privateBadge = row.querySelector('.badge-private');
                        if (privateBadge) {
                            privateBadge.style.display = updatedUrlData.private_stats ? 'inline-flex' : 'none';
                        }

                        // Add update animation
                        row.style.transition = 'all 0.3s ease';
                        row.style.background = 'rgba(16, 185, 129, 0.1)';
                        setTimeout(() => {
                            row.style.background = '';
                        }, 1000);
                    }
                } catch (error) {
                    console.error('Error parsing URL data for update:', error);
                }
            }
        });
    }

    refreshUrlList() {
        // Trigger a refresh of the URL list
        if (window.fetchData && typeof window.fetchData === 'function') {
            window.fetchData();
        }
    }
}

// Initialize URL manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.urlManager = new UrlManager();
});

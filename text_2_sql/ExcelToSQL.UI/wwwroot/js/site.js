// Global namespace
var ExcelToSQL = ExcelToSQL || {};

// API Configuration
ExcelToSQL.Config = {
    apiBaseUrl: '', // Will be set from server config
    endpoints: {
        upload: '/api/upload',
        query: '/api/query',
        files: '/api/files',
        delete: '/api/files'
    }
};

// API Service
ExcelToSQL.API = {
    // Generic AJAX helpers
    postJSON: function(url, data) {
        return $.ajax({
            url: url,
            type: "POST",
            contentType: "application/json;charset=utf-8",
            dataType: "json",
            data: JSON.stringify(data)
        });
    },

    getJSON: function(url) {
        return $.ajax({
            url: url,
            type: "GET",
            contentType: "application/json;charset=utf-8",
            dataType: "json"
        });
    },

    deleteJSON: function(url) {
        return $.ajax({
            url: url,
            type: "DELETE",
            contentType: "application/json;charset=utf-8",
            dataType: "json"
        });
    },

    // API specific methods
    uploadFile: function(formData, onProgress) {
        return $.ajax({
            url: ExcelToSQL.Config.endpoints.upload,
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            xhr: function() {
                var xhr = new window.XMLHttpRequest();
                if (onProgress) {
                    xhr.upload.addEventListener('progress', function(evt) {
                        if (evt.lengthComputable) {
                            var percentComplete = evt.loaded / evt.total;
                            onProgress(percentComplete);
                        }
                    }, false);
                }
                return xhr;
            }
        });
    },

    queryData: function(query) {
        return this.postJSON(ExcelToSQL.Config.endpoints.query, { query: query });
    },

    getFiles: function() {
        return this.getJSON(ExcelToSQL.Config.endpoints.files);
    },

    deleteFile: function(fileId) {
        return this.deleteJSON(`${ExcelToSQL.Config.endpoints.delete}/${fileId}`);
    }
};

// UI Utilities
ExcelToSQL.UI = {
    showLoading: function() {
        if (!this.loadingElement) {
            this.loadingElement = $('<div>')
                .addClass('loading-overlay')
                .append($('<div>').addClass('loading'));
            $('body').append(this.loadingElement);
        }
        this.loadingElement.show();
    },

    hideLoading: function() {
        if (this.loadingElement) {
            this.loadingElement.hide();
        }
    },

    showMessage: function(message, type = 'success') {
        const alertDiv = $('<div>')
            .addClass(`alert alert-${type} alert-dismissible fade show`)
            .attr('role', 'alert')
            .html(`
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            `);

        // Remove any existing alerts
        $('.alert').remove();

        // Add the new alert
        $('.container').first().prepend(alertDiv);

        // Auto dismiss after 5 seconds
        setTimeout(() => {
            alertDiv.alert('close');
        }, 5000);
    },

    formatBytes: function(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';

        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];

        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    },

    formatDate: function(date) {
        return new Date(date).toLocaleString();
    }
};

// Event Handlers
ExcelToSQL.Events = {
    onApiError: function(error) {
        console.error('API Error:', error);
        let errorMessage = 'An unexpected error occurred';
        
        if (error.responseJSON && error.responseJSON.message) {
            errorMessage = error.responseJSON.message;
        } else if (error.statusText) {
            errorMessage = error.statusText;
        }
        
        ExcelToSQL.UI.showMessage(errorMessage, 'danger');
    }
};

// Initialize on document ready
$(document).ready(function() {
    // Setup global AJAX error handling
    $(document).ajaxError(function(event, jqXHR, settings, error) {
        ExcelToSQL.Events.onApiError(jqXHR);
    });

    // Setup global AJAX loading indicator
    $(document).ajaxStart(function() {
        ExcelToSQL.UI.showLoading();
    });

    $(document).ajaxStop(function() {
        ExcelToSQL.UI.hideLoading();
    });
});

// Prevent form submissions on enter key
$(document).on('keypress', 'form', function(event) {
    return event.keyCode != 13;
});

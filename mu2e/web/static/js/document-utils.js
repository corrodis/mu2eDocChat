/**
 * Shared utility functions for document handling
 */

async function summarizeFile(docid, fileIndex) {
    const summaryElement = document.getElementById(`summary-${fileIndex}`);
    
    try {
        const requestData = {
            fileIndex: fileIndex,
            instructions: 'You are a helpful assistant that summarizes documents in one paragraph. Do not include any other text than the summary.'
        };

        const response = await fetch(`/api/summary/${docid}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const summary = await response.text();
        
        // Update the summary in the DOM
        summaryElement.innerHTML = `
            <strong>AI Summary:</strong> 
            <span style="color: #2c3e50;">${escapeHtml(summary)}</span>
        `;
        
    } catch (error) {
        console.error('Error generating summary:', error);
        
        // Show error message in the DOM
        summaryElement.innerHTML = `
            <strong>AI Summary:</strong> 
            <span style="color: #e74c3c; font-style: italic;">Failed to generate summary</span>
        `;
    }
}

async function summarizeSearchResult(docid, resultIndex, fileIndex, query) {
    const summaryElement = document.getElementById(`summary-content-${resultIndex}`);
    
    try {
        const requestData = {
            fileIndex: fileIndex,
            instructions: `You are a helpful assistant that summarizes documents in roughly one sentence. Do not include any other text than the summary. Keep in mind, the user is looking for: ${query}`
        };

        const response = await fetch(`/api/summary/${docid}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const summary = await response.text();
        
        // Update the summary in the DOM
        summaryElement.innerHTML = `
            <strong>AI Summary:</strong> <span style="color: #2c3e50;">${escapeHtml(summary)}</span>
        `;
        
    } catch (error) {
        console.error('Error generating summary for search result:', error);
        
        // Show error message
        summaryElement.innerHTML = `
            <strong>AI Summary:</strong> <span style="color: #e74c3c; font-style: italic;">Failed to generate summary</span>
        `;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toggleVisibility(id) {
    var element = document.getElementById(id);
    var button = document.getElementById(id+"-button");
    if (element.style.display === 'none') {
      element.style.display = 'block';
      button.innerHTML = "hide"
    } else {
      element.style.display = 'none';
      button.innerHTML = "show"
    }
  }

function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

// Function to start chat with document (navigates to chat page)
function startChatWithDocument(docId) {
    if (!docId) return;
    
    // Store the docId to start chat with when chat page loads
    sessionStorage.setItem('startChatWithDoc', docId);
    
    // Navigate to chat page
    window.location.href = '/chat';
}
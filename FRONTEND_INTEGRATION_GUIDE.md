# Frontend Integration Guide for File Storage

## Problem Identified

The file import/export backend endpoints (`/import`, `/export`, `/list/{session_id}`) are implemented but **not being called by the frontend**. Currently:

1. Frontend parses files locally (client-side only)
2. Only logs operations to `/logs/operation` 
3. Files are NOT saved to the backend storage
4. Result: Empty `workspace/files/` directories

## Solution: Update Frontend to Call Backend Endpoints

### Step 1: Add File Storage Service

Create `packages/frontend/src/services/fileStorageService.js`:

```javascript
/**
 * Service for file import/export operations with backend storage
 */

const API_BASE_URL = ''; // Relative path, proxied by Vite

/**
 * Import a file to backend storage
 * @param {string} content - File content as string
 * @param {string} filename - File name
 * @param {string} sessionId - Session ID  
 * @param {string} userId - User ID
 * @param {string} format - File format (optional)
 * @returns {Promise<Object>} Result with file paths
 */
export const importFile = async (content, filename, sessionId, userId, format = null) => {
    const response = await fetch(`${API_BASE_URL}/import`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            content,
            filename,
            sessionId,
            userId,
            format
        })
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to import file');
    }

    return response.json();
};

/**
 * Export a file from backend storage
 * @param {string} filename - File name to export
 * @param {string} sessionId - Session ID
 * @param {string} userId - User ID
 * @returns {Promise<Object>} Result with file content
 */
export const exportFile = async (filename, sessionId, userId) => {
    const response = await fetch(`${API_BASE_URL}/export`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            filename,
            sessionId,
            userId
        })
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to export file');
    }

    return response.json();
};

/**
 * List all files in a session
 * @param {string} sessionId - Session ID
 * @returns {Promise<Object>} List of files
 */
export const listFiles = async (sessionId) => {
    const response = await fetch(`${API_BASE_URL}/list/${sessionId}`);

    if (!response.ok) {
        throw new Error('Failed to list files');
    }

    return response.json();
};

export const fileStorageService = {
    importFile,
    exportFile,
    listFiles
};
```

### Step 2: Update vite.config.js

Add the new endpoints to the proxy configuration in `packages/frontend/vite.config.js`:

```javascript
server: {
  proxy: {
    // ... existing proxies ...
    '/import': {
      target: 'http://localhost:3000',
      changeOrigin: true,
      secure: false,
    },
    '/export': {
      target: 'http://localhost:3000',
      changeOrigin: true,
      secure: false,
    },
    '/list': {
      target: 'http://localhost:3000',
      changeOrigin: true,
      secure: false,
    }
  }
}
```

### Step 3: Update MolecularContext.jsx

Modify the `importFile` function in `packages/frontend/src/context/MolecularContext.jsx` to call the backend:

```javascript
import { fileStorageService } from '../services/fileStorageService';

// Inside MolecularContext component:

const importFile = async (file, createNewLayer) => {
    const { newAtoms, newLat, isPdb, text } = await parseFile(file);
    if (isPdb) setPdbContent(text);
    
    const newIds = addAtoms(newAtoms, newLat, createNewLayer);
    
    recordOp('IMPORT_FILE', {
        fileName: file.name,
        createNewLayer,
        atomCount: newAtoms.length,
        hasLattice: Boolean(newLat),
        layerId: newIds.layerId
    });
    
    // NEW: Save file to backend storage
    try {
        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const content = e.target.result;
                await fileStorageService.importFile(
                    content,
                    file.name,
                    sessionState.sessionId || 'ui',
                    sessionState.userId || 'guest',
                    null // Let backend detect format
                );
                console.log('File saved to backend storage:', file.name);
            } catch (error) {
                console.warn('Failed to save file to backend:', error);
                // Non-fatal - don't block the import
            }
        };
        reader.readAsText(file);
    } catch (error) {
        console.warn('Failed to initiate file storage:', error);
    }
    
    setSelectedAtomIds(newIds);
};
```

### Step 4: Update handleDownload (Optional)

If you want to save exported POSCAR files to backend storage:

```javascript
const handleDownload = async () => {
    // ... existing POSCAR generation code ...
    
    // Download to user
    const blob = new Blob([s], {type: 'text/plain'});
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'structure.poscar';
    link.click();
    URL.revokeObjectURL(link.href);
    
    // NEW: Also save to backend storage
    try {
        await fileStorageService.importFile(
            s,
            'exported_structure.poscar',
            sessionState.sessionId || 'ui',
            sessionState.userId || 'guest',
            'poscar'
        );
        console.log('Export saved to backend storage');
    } catch (error) {
        console.warn('Failed to save export to backend:', error);
    }
};
```

### Step 5: Add File Management UI (Optional)

Create a component to view and download stored files:

```javascript
// packages/frontend/src/components/FileManager.jsx
import React, { useState, useEffect } from 'react';
import { fileStorageService } from '../services/fileStorageService';

export function FileManager({ sessionId }) {
    const [files, setFiles] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadFiles();
    }, [sessionId]);

    const loadFiles = async () => {
        try {
            setLoading(true);
            const result = await fileStorageService.listFiles(sessionId);
            setFiles(result.files || []);
        } catch (error) {
            console.error('Failed to load files:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = async (filename) => {
        try {
            const result = await fileStorageService.exportFile(
                filename,
                sessionId,
                'user'
            );
            
            // Download file
            const blob = new Blob([result.content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Failed to download file:', error);
        }
    };

    if (loading) return <div>Loading files...</div>;

    return (
        <div className="file-manager">
            <h3>Session Files ({files.length})</h3>
            <ul>
                {files.map(file => (
                    <li key={file.filename}>
                        <span>{file.filename}</span>
                        <span>{(file.size / 1024).toFixed(2)} KB</span>
                        <button onClick={() => handleDownload(file.filename)}>
                            Download
                        </button>
                    </li>
                ))}
            </ul>
        </div>
    );
}
```

## Benefits After Integration

1. ✅ All imported files automatically saved to backend
2. ✅ Files stored separately from agent workspace
3. ✅ Auto-conversion to ExtXYZ format
4. ✅ Complete audit trail in operation logs
5. ✅ Files can be retrieved across sessions
6. ✅ Proper session-based file organization

## Testing After Integration

Once frontend is updated, test with:

```bash
# Start middleware (if not running)
cd packages/middleware
python main.py

# Start frontend (in another terminal)
cd packages/frontend
npm run dev

# Import a file through the UI
# Check backend storage:
ls workspace/files/s_*/
```

You should see:
- Original file (e.g., `structure.cif`)
- Converted ExtXYZ file (e.g., `structure.extxyz`)
- Operation logs in `workspace/logs/`

## Current Status

✅ Backend endpoints implemented and working  
✅ Directory structure created automatically  
❌ **Frontend not calling endpoints yet** ← This is why you see empty folders  
❌ Frontend integration pending

The backend code is correct and functional - it just needs the frontend to call it!

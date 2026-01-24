# File Storage System Usage

## Overview

The file storage system allows you to import and export user files separately from the agent workspace. Each session has its own subfolder at `workspace/files/{session_id}/`, keeping user files isolated from agent operations.

## Directory Structure

```
workspace/
  ├── logs/                          # Operation logs (shared)
  ├── files/                         # User files (shared)
  │   ├── s_abc123/                  # Session-specific files
  │   │   ├── imported_file.cif
  │   │   ├── imported_file.extxyz   # Auto-converted
  │   │   └── exported_data.xyz
  │   └── s_def456/
  │       └── structure.poscar
  └── 20260124_090014-s_abc123/      # Agent workspace (inputs/outputs)
      ├── inputs/
      ├── outputs/
      └── tmp/
```

## Features

### 1. Automatic ExtXYZ Conversion
When you import a readable structure file (CIF, POSCAR, XYZ, PDB, etc.), the system:
- Saves the original file
- Automatically converts it to ExtXYZ format using ASE
- Stores both versions in the session's files folder

Supported formats for conversion:
- CIF (`.cif`)
- POSCAR/VASP (`.poscar`, `.vasp`, `POSCAR`)
- XYZ (`.xyz`)
- PDB (`.pdb`)
- ExtXYZ (`.extxyz`)

### 2. Operation Logging
All import/export operations are automatically logged to the operation log with:
- Timestamp
- Operation type (import/export)
- Filename and format
- File paths (original and converted)
- Session ID and User ID

## API Endpoints

### Import File
**POST** `/import`

Import a file into the session's files directory.

```json
{
  "content": "file content as string",
  "filename": "structure.cif",
  "sessionId": "s_abc123",
  "userId": "u_user123",
  "format": "cif"  // optional, auto-detected if not provided
}
```

Response:
```json
{
  "status": "success",
  "message": "File imported successfully",
  "files": {
    "original": "/path/to/workspace/files/s_abc123/structure.cif",
    "extxyz": "/path/to/workspace/files/s_abc123/structure.extxyz",
    "format": "cif"
  }
}
```

### Export File
**POST** `/export`

Export a file from the session's files directory.

```json
{
  "filename": "structure.extxyz",
  "sessionId": "s_abc123",
  "userId": "u_user123"
}
```

Response:
```json
{
  "filename": "structure.extxyz",
  "content": "file content as string",
  "path": "/path/to/workspace/files/s_abc123/structure.extxyz"
}
```

### List Files
**GET** `/list/{session_id}`

List all files in a session's files directory.

Response:
```json
{
  "sessionId": "s_abc123",
  "files": [
    {
      "filename": "structure.cif",
      "size": 1024,
      "modified": "2026-01-24T10:30:00",
      "path": "/path/to/workspace/files/s_abc123/structure.cif"
    },
    {
      "filename": "structure.extxyz",
      "size": 2048,
      "modified": "2026-01-24T10:30:01",
      "path": "/path/to/workspace/files/s_abc123/structure.extxyz"
    }
  ]
}
```

## Operation Log Format

File operations are logged to `workspace/logs/operations_{date}_{session_id}.log` in JSON Lines format:

```json
{
  "timestamp": "2026-01-24T10:30:00.123456",
  "operation": "file_import",
  "metadata": {
    "sessionId": "s_abc123",
    "userId": "u_user123",
    "filename": "structure.cif",
    "operationType": "import",
    "format": "cif",
    "filePaths": {
      "original": "/path/to/workspace/files/s_abc123/structure.cif",
      "extxyz": "/path/to/workspace/files/s_abc123/structure.extxyz"
    }
  }
}
```

## Frontend Integration Example

```javascript
// Import a file
async function importFile(file, sessionId, userId) {
  const content = await file.text();
  const response = await fetch('/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content: content,
      filename: file.name,
      sessionId: sessionId,
      userId: userId
    })
  });
  return response.json();
}

// List session files
async function listFiles(sessionId) {
  const response = await fetch(`/list/${sessionId}`);
  return response.json();
}

// Export a file
async function exportFile(filename, sessionId, userId) {
  const response = await fetch('/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename: filename,
      sessionId: sessionId,
      userId: userId
    })
  });
  const data = await response.json();
  
  // Download the file
  const blob = new Blob([data.content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
```

## Benefits

1. **Isolation**: User files are separate from agent workspace, preventing accidental modification or deletion by agents
2. **Automatic Conversion**: ExtXYZ format is automatically generated for interoperability
3. **Audit Trail**: All file operations are logged with metadata
4. **Session Management**: Files are organized by session for easy tracking and cleanup
5. **Format Detection**: Automatically detects file formats from extension or content

## Notes

- Files are stored in UTF-8 encoding
- Binary files are not currently supported (only text-based structure files)
- The ExtXYZ conversion uses ASE library and may fail for malformed or unsupported formats
- If conversion fails, the original file is still saved successfully
- Session directories are created automatically when needed

// src/components/FileUpload.js (New "Drop Zone" Version)

import React from 'react';
import './FileUpload.css'; // We will use the CSS we already wrote

function FileUpload({ jdFile, setJdFile, resumeFiles, setResumeFiles }) {

  const handleJdChange = (event) => {
    if (event.target.files.length) {
      setJdFile(event.target.files[0]);
    }
  };

  const handleResumesChange = (event) => {
    if (event.target.files.length) {
      setResumeFiles(Array.from(event.target.files));
    }
  };

  return (
    <div className="file-upload-container">
      {/* Job Description Upload Area */}
      <div className="upload-box">
        {/* The <label> now acts as the clickable area */}
        <label htmlFor="jd-upload" className="upload-label">
          <h3>1. Upload Job Description</h3>
          <p className="file-name-display">
            {jdFile ? jdFile.name : 'Click or drag a file here'}
          </p>
        </label>
        <input
          id="jd-upload"
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={handleJdChange}
        />
      </div>

      {/* Resumes Upload Area */}
      <div className="upload-box">
        <label htmlFor="resumes-upload" className="upload-label">
          <h3>2. Upload Resumes</h3>
          <p className="file-name-display">
            {resumeFiles.length > 0 ? `${resumeFiles.length} file(s) selected` : 'Click or drag files here'}
          </p>
        </label>
        <input
          id="resumes-upload"
          type="file"
          accept=".pdf,.docx"
          multiple // This allows selecting multiple files
          onChange={handleResumesChange}
        />
      </div>
    </div>
  );
}

export default FileUpload;
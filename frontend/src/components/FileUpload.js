// src/components/FileUpload.js (New "Drop Zone" Version)

import React from 'react';
import './FileUpload.css';

function FileUpload({ jdFile, setJdFile, resumeFiles, setResumeFiles }) {
  const buildFileKey = (file) => `${file.name}::${file.size}::${file.lastModified}`;

  const handleJdChange = (event) => {
    const file = event.target.files?.[0];
    if (file) {
      setJdFile(file);
    }
    // Reset the input so selecting the same file again re-triggers onChange
    event.target.value = '';
  };

  const handleClearJd = () => {
    setJdFile(null);
  };

  const handleResumesChange = (event) => {
    const incoming = Array.from(event.target.files || []);
    if (incoming.length === 0) {
      return;
    }

    const deduped = new Map(resumeFiles.map((file) => [buildFileKey(file), file]));
    incoming.forEach((file) => {
      const key = buildFileKey(file);
      if (!deduped.has(key)) {
        deduped.set(key, file);
      }
    });

    setResumeFiles(Array.from(deduped.values()));
    event.target.value = '';
  };

  const handleRemoveResume = (fileKey) => {
    setResumeFiles(resumeFiles.filter((file) => buildFileKey(file) !== fileKey));
  };

  return (
    <div className="file-upload-container">
      {/* Job Description Upload Area */}
      <div className="upload-box">
        <label htmlFor="jd-upload" className="upload-label">
          <h3>1. Upload Job Description</h3>
          <p className="upload-instructions">
            Accepts PDF, DOCX or TXT. Use the Tata Strive JD format for best skill extraction.
          </p>
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
        {jdFile && (
          <div className="selected-meta">
            <span className="selected-pill">{jdFile.name}</span>
            <button
              type="button"
              className="pill-action"
              onClick={handleClearJd}
            >
              Remove JD
            </button>
          </div>
        )}
      </div>

      {/* Resumes Upload Area */}
      <div className="upload-box">
        <label htmlFor="resumes-upload" className="upload-label">
          <h3>2. Upload Resumes</h3>
          <p className="upload-instructions">
            Add one or more candidate resumes. Upload PDFs or DOCX exports from the LMS/Canva.
          </p>
          <p className="file-name-display">
            {resumeFiles.length > 0 ? `${resumeFiles.length} file(s) selected` : 'Click or drag files here'}
          </p>
        </label>
        <input
          id="resumes-upload"
          type="file"
          accept=".pdf,.docx"
          multiple
          onChange={handleResumesChange}
        />

        {resumeFiles.length > 0 && (
          <ul className="resume-list">
            {resumeFiles.map((file) => {
              const key = buildFileKey(file);
              return (
                <li key={key} className="resume-pill">
                  <span className="pill-name" title={file.name}>{file.name}</span>
                  <button
                    type="button"
                    className="pill-action"
                    onClick={(event) => {
                      event.stopPropagation();
                      handleRemoveResume(key);
                    }}
                  >
                    Remove
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

export default FileUpload;

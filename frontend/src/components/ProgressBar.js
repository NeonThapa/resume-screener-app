// src/components/ProgressBar.js
import React from 'react';
import './ProgressBar.css';

function ProgressBar({ message, detail }) {
  return (
    <div className="progress-container">
      <div className="progress-bar"></div>
      <p className="progress-text">{message || 'Analyzing Resumes...'}</p>
      {detail && <p className="progress-subtext">{detail}</p>}
    </div>
  );
}

export default ProgressBar;

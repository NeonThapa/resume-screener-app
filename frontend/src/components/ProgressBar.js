// src/components/ProgressBar.js
import React from 'react';
import './ProgressBar.css';

function ProgressBar() {
  return (
    <div className="progress-container">
      <div className="progress-bar"></div>
      <p className="progress-text">Analyzing Resumes...</p>
    </div>
  );
}

export default ProgressBar;
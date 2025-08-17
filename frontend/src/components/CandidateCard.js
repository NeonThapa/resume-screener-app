// src/components/CandidateCard.js (Final Version)
import React, { useState } from 'react';
import './CandidateCard.css';

// The component now receives the file URL as a prop for the "View Resume" button
function CandidateCard({ candidate, fileUrl }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const handleCardClick = (e) => {
    // This prevents the card from closing when the "View Resume" button is clicked
    if (e.target.tagName !== 'A') {
      setIsExpanded(!isExpanded);
    }
  };

  const score = candidate.final_score || 0;

  // Create "safe" variables to prevent crashes if data is missing
  const details = candidate.details || {};
  const matchedSkills = details.matched_skills || [];
  const missingSkills = details.missing_skills || [];
  const aiSummary = details.ai_summary || "No summary was generated.";
  const calculatedYears = details.calculated_years; // Can be 0, which is fine

  return (
    <div className={`candidate-card ${isExpanded ? 'expanded' : ''}`} onClick={handleCardClick}>
      <div className="card-header">
        <span className="rank">#{candidate.rank}</span>
        <h3 className="filename">{candidate.filename}</h3>
        <span className="score">{score}%</span>
      </div>

      {isExpanded && (
        <div className="card-details">
          
          {/* AI Summary Section */}
          <h4>AI Analysis Summary:</h4>
          <p className="ai-summary">{aiSummary}</p>

          {/* Key Metrics Section */}
          <div className="metrics-container">
            <h4>Calculated Experience:</h4>
            <p className="metric-value">{calculatedYears} years</p>
          </div>

          {/* Matched Skills Section */}
          <h4>Matched Skills ({matchedSkills.length}):</h4>
          <div className="skills-list">
            {matchedSkills.length > 0 ? (
              matchedSkills.map(skill => (
                <span key={skill} className="skill-tag matched">{skill}</span>
              ))
            ) : (
              <p className="no-skills-text">None of the required skills were found.</p>
            )}
          </div>

          {/* Missing Skills Section */}
          <h4>Missing Skills ({missingSkills.length}):</h4>
          <div className="skills-list">
            {missingSkills.length > 0 ? (
              missingSkills.map(skill => (
                <span key={skill} className="skill-tag missing">{skill}</span>
              ))
            ) : (
              <p className="no-skills-text">No missing skills identified.</p>
            )}
          </div>

          {/* View Resume Button */}
          <div className="button-wrapper">
            <a href={fileUrl} target="_blank" rel="noopener noreferrer" className="view-resume-button" onClick={(e) => e.stopPropagation()}>
              View Resume
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

export default CandidateCard;
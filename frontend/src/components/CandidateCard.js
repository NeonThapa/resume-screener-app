// src/components/CandidateCard.js
import React, { useState } from 'react';
import './CandidateCard.css';

function CandidateCard({ candidate, fileUrl }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showDeepInsights, setShowDeepInsights] = useState(false);

  const handleCardClick = (event) => {
    if (event.target.tagName !== 'A') {
      const nextExpanded = !isExpanded;
      setIsExpanded(nextExpanded);
      if (!nextExpanded) {
        setShowDeepInsights(false);
      }
    }
  };

  const score = Number.isFinite(candidate.final_score) ? candidate.final_score : 0;
  const details = candidate.details || {};

  const matchedCoreSkills = details.core_skill_matches || [];
  const matchedSupportSkills = details.support_skill_matches || [];
  const matchedSkills = details.matched_skills || [...matchedCoreSkills, ...matchedSupportSkills];
  const missingCoreSkills = details.missing_skills || [];
  const missingOptionalSkills = details.missing_optional_skills || [];

  const aiSummary = details.ai_summary || 'No summary was generated.';
  const calculatedYears = details.calculated_years !== undefined ? details.calculated_years : 'n/a';
  const recentYears = details.recent_years !== undefined ? details.recent_years : null;

  const strengths = details.strengths || [];
  const risks = details.risks || [];
  const recommendations = details.recommendations || [];
  const experienceSegments = details.experience_segments || [];
  const employmentGaps = details.employment_gaps || [];
  const highlightedKeywords = details.highlighted_keywords || [];
  const educationHighlights = details.education_highlights || [];
  const certificationHighlights = details.certifications || [];
  const summaryHighlights = details.summary_highlights || [];
  const deepInsights = details.deep_insights || null;
  const aiAssessment = details.ai_assessment || null;

  const scoreBreakdown = details.score_breakdown || {};
  const bonusPenalty = typeof scoreBreakdown.bonus_or_penalty === 'number' ? scoreBreakdown.bonus_or_penalty : 0;
  const penaltyReasons = Array.isArray(scoreBreakdown.penalties) ? scoreBreakdown.penalties : [];

  const engineUsed = candidate.engine_used || 'rule';

  return (
    <div className={`candidate-card ${isExpanded ? 'expanded' : ''}`} onClick={handleCardClick}>
      <div className="card-header">
        <span className="rank">#{candidate.rank}</span>
        <h3 className="filename">{candidate.filename}</h3>
        <span className="score">{score}%</span>
      </div>

      {isExpanded && (
        <div className="card-details">
          <div className="meta-strip">
            <span className="engine-pill">{engineUsed === 'ai' ? 'LLM Analysis' : 'Rule-Based Analysis (legacy)'}</span>
          </div>

          <h4>Fit Summary</h4>
          <p className="ai-summary">{aiSummary}</p>

          <div className="metrics-container">
            <div className="metric-block">
              <span className="metric-label">Calculated Experience</span>
              <span className="metric-value">{calculatedYears} years</span>
            </div>
            {typeof recentYears === 'number' && (
              <div className="metric-block">
                <span className="metric-label">Recent (&lt;5 yr) Experience</span>
                <span className="metric-value">{recentYears} years</span>
              </div>
            )}
          </div>

          <h4>Core JD Skills ({matchedCoreSkills.length}):</h4>
          <div className="skills-list">
            {matchedCoreSkills.length > 0 ? (
              matchedCoreSkills.map((skill) => (
                <span key={skill} className="skill-tag matched">{skill}</span>
              ))
            ) : (
              <p className="no-skills-text">No core JD skills matched yet.</p>
            )}
          </div>

          <h4>Supporting Skills ({matchedSupportSkills.length}):</h4>
          <div className="skills-list">
            {matchedSupportSkills.length > 0 ? (
              matchedSupportSkills.map((skill) => (
                <span key={skill} className="skill-tag matched secondary">{skill}</span>
              ))
            ) : (
              <p className="no-skills-text">No supporting skills recorded.</p>
            )}
          </div>

          <h4>Missing Core Skills ({missingCoreSkills.length}):</h4>
          <div className="skills-list">
            {missingCoreSkills.length > 0 ? (
              missingCoreSkills.map((skill) => (
                <span key={skill} className="skill-tag missing">{skill}</span>
              ))
            ) : (
              <p className="no-skills-text">No missing core skills identified.</p>
            )}
          </div>

          {missingOptionalSkills.length > 0 && (
            <>
              <h4>Missing Supporting Skills ({missingOptionalSkills.length}):</h4>
              <div className="skills-list">
                {missingOptionalSkills.map((skill) => (
                  <span key={skill} className="skill-tag missing subtle">{skill}</span>
                ))}
              </div>
            </>
          )}

          {penaltyReasons.length > 0 && (
            <div className="insight-banner warning">
              <h4>Penalty Drivers</h4>
              <ul className="insight-list warning">
                {penaltyReasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          )}

          {bonusPenalty !== 0 && (
            <div className="insight-banner neutral">
              <span className="metric-label">Bonus / Penalty Adjustment</span>
              <span className="metric-value">{bonusPenalty > 0 ? '+' : ''}{bonusPenalty.toFixed(1)} pts</span>
            </div>
          )}

          {(strengths.length > 0 || risks.length > 0 || recommendations.length > 0) && (
            <div className="insight-grid">
              {strengths.length > 0 && (
                <div>
                  <h4>Strengths</h4>
                  <ul className="insight-list">
                    {strengths.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              )}
              {risks.length > 0 && (
                <div>
                  <h4>Risks / Watchouts</h4>
                  <ul className="insight-list warning">
                    {risks.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              )}
              {recommendations.length > 0 && (
                <div>
                  <h4>Recommended Follow-ups</h4>
                  <ul className="insight-list neutral">
                    {recommendations.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {experienceSegments.length > 0 && (
            <>
              <h4>Experience Timeline</h4>
              <ul className="timeline-list">
                {experienceSegments.map((segment) => (
                  <li key={`${segment.start}-${segment.end}`}>
                    <div className="timeline-top">
                      <span className="timeline-range">{segment.start} -> {segment.end}</span>
                      <span className="timeline-duration">{segment.duration_years} yrs</span>
                    </div>
                    {segment.company && (
                      <span className="timeline-company">{segment.company}</span>
                    )}
                    <span className="timeline-label">{segment.label}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {employmentGaps.length > 0 && (
            <>
              <h4>Detected Employment Gaps</h4>
              <ul className="insight-list warning">
                {employmentGaps.map((gap) => (
                  <li key={`${gap.start}-${gap.end}`}>
                    {gap.months} months between {gap.start} and {gap.end}
                  </li>
                ))}
              </ul>
            </>
          )}

          {(educationHighlights.length > 0 || certificationHighlights.length > 0 || summaryHighlights.length > 0) && (
            <div className="insight-grid">
              {educationHighlights.length > 0 && (
                <div>
                  <h4>Education Highlights</h4>
                  <ul className="insight-list">
                    {educationHighlights.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              )}
              {certificationHighlights.length > 0 && (
                <div>
                  <h4>Certifications</h4>
                  <ul className="insight-list neutral">
                    {certificationHighlights.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              )}
              {summaryHighlights.length > 0 && (
                <div>
                  <h4>Profile Snapshot</h4>
                  <ul className="insight-list">
                    {summaryHighlights.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {aiAssessment && (
            <div className="ai-assessment">
              <h4>AI Assessment Overlay</h4>
              {aiAssessment.error ? (
                <p className="ai-error">AI engine feedback: {aiAssessment.error}</p>
              ) : (
                <ul className="insight-list">
                  <li>AI Suitability Score: {aiAssessment.final_score ?? 'n/a'}%</li>
                  {Array.isArray(aiAssessment.matched_skills) && aiAssessment.matched_skills.length > 0 && (
                    <li>AI Matched Skills: {aiAssessment.matched_skills.slice(0, 6).join(', ')}</li>
                  )}
                  {aiAssessment.ai_summary && <li>{aiAssessment.ai_summary}</li>}
                </ul>
              )}
            </div>
          )}

          {deepInsights && (
            <div className="deep-insights">
              <button
                className="toggle-deep"
                onClick={(event) => {
                  event.stopPropagation();
                  setShowDeepInsights(!showDeepInsights);
                }}
              >
                {showDeepInsights ? 'Hide Deep Insights' : 'Show Deep Insights'}
              </button>
              {showDeepInsights && (
                <div className="deep-content">
                  {Array.isArray(deepInsights.notable_sentences) && deepInsights.notable_sentences.length > 0 && (
                    <>
                      <h4>Notable Accomplishments</h4>
                      <ul className="insight-list">
                        {deepInsights.notable_sentences.map((sentence) => (
                          <li key={sentence}>{sentence}</li>
                        ))}
                      </ul>
                    </>
                  )}
                  {Array.isArray(deepInsights.recommended_questions) && deepInsights.recommended_questions.length > 0 && (
                    <>
                      <h4>Suggested Interview Prompts</h4>
                      <ul className="insight-list neutral">
                        {deepInsights.recommended_questions.map((question) => (
                          <li key={question}>{question}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="button-wrapper">
            <a
              href={fileUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="view-resume-button"
              onClick={(event) => event.stopPropagation()}
            >
              View Resume
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

export default CandidateCard;

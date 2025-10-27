import React from 'react';
import './JDOverview.css';

const HIGHLIGHT_ORDER = [
  'ROLE SUMMARY',
  'POSITION OVERVIEW',
  'KEY RESPONSIBILITIES',
  'PRIMARY RESPONSIBILITIES',
  'QUALIFICATIONS',
  'REQUIREMENTS',
  'SKILLS',
  'TECH STACK',
  'TOOLS & TECHNOLOGIES',
];

function JDOverview({ sections }) {
  if (!sections || Object.keys(sections).length === 0) {
    return null;
  }

  const orderedSections = HIGHLIGHT_ORDER.filter((title) => sections[title]);
  const remaining = Object.keys(sections).filter(
    (title) => !HIGHLIGHT_ORDER.includes(title) && sections[title]
  );

  const displayList = [...orderedSections, ...remaining].slice(0, 6);

  return (
    <section className="jd-overview">
      <div className="jd-header">
        <h2>Job Profile Snapshot</h2>
        <p>Key highlights extracted from the uploaded job description.</p>
      </div>
      <div className="jd-grid">
        {displayList.map((title) => (
          <article key={title} className="jd-card">
            <h3>{title.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())}</h3>
            <p>{sections[title]}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export default JDOverview;
